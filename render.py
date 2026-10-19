#!/usr/bin/env python3
"""Build hyprlock's native config from editable component settings."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from PIL import Image

ROOT = Path.home() / '.config/hypr/lockscreen'
SETTINGS = ROOT / 'settings.toml'
OUTPUT = Path.home() / '.config/hypr/hyprlock.conf'
COMPONENTS = ('avatar', 'clock', 'date', 'greeting', 'password', 'music', 'weather', 'battery')
ANCHORS = {
    'top-left': (0, 0), 'top-center': (.5, 0), 'top-right': (1, 0),
    'center-left': (0, .5), 'center': (.5, .5), 'center-right': (1, .5),
    'bottom-left': (0, 1), 'bottom-center': (.5, 1), 'bottom-right': (1, 1),
}
REL = ('below', 'above', 'left-of', 'right-of')


def block(kind, **values):
    return kind + ' {\n' + ''.join(f'    {k} = {v}\n' for k, v in values.items()) + '}\n'


def quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def prepare_avatar(source):
    target = Path.home() / '.cache/ml4w/lockscreen-avatar.png'
    if not Path(source).is_file():
        raise ValueError('avatar image missing: ' + source)
    try:
        with Image.open(source) as image:
            image = image.convert('RGB')
            image.thumbnail((400, 400))
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix('.tmp.png')
            image.save(temporary)
            temporary.replace(target)
    except (OSError, ValueError) as exc:
        raise ValueError('avatar image unreadable: ' + source) from exc
    return target


def monitor_size():
    try:
        monitors = json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'], timeout=3))
        active = next((m for m in monitors if m.get('focused')), monitors[0])
        return int(active['width'] / active.get('scale', 1)), int(active['height'] / active.get('scale', 1))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError, KeyError):
        return 1920, 1080


def render(settings, dims, wallpaper):
    w, h = dims
    sx, sy = w / 1920, h / 1080
    centers, sizes, visiting = {}, {}, set()
    for name in COMPONENTS:
        cfg = settings[name]
        if type(cfg.get('enabled')) is not bool:
            raise ValueError(f'{name}.enabled must be true or false')
        size = cfg.get('size')
        if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
            raise ValueError(f'{name}.size must be [positive_width, positive_height]')
        sizes[name] = (round(size[0]*sx), round(size[1]*sy))

    def center(name):
        if name in centers:
            return centers[name]
        if name in visiting:
            raise ValueError('circular component placement at ' + name)
        visiting.add(name)
        cfg = settings[name]
        keys = [k for k in ('anchor', *REL) if k in cfg]
        if len(keys) != 1:
            raise ValueError(f'{name}: choose exactly one anchor or relative placement')
        key = keys[0]
        sw, sh = sizes[name]
        if key == 'anchor':
            if cfg[key] not in ANCHORS:
                raise ValueError(f'{name}: invalid anchor {cfg[key]}')
            ax, ay = ANCHORS[cfg[key]]
            x = ax * w + (sw/2 if ax == 0 else -sw/2 if ax == 1 else 0)
            y = ay * h + (sh/2 if ay == 0 else -sh/2 if ay == 1 else 0)
        else:
            parent = cfg[key]
            if parent not in COMPONENTS:
                raise ValueError(f'{name}: {key} target must be a component')
            # Hidden components can still serve as layout guides for dependents.
            px, py = center(parent)
            pw, ph = sizes[parent]
            x, y = px, py
            if key == 'below': y += (ph + sh)/2
            if key == 'above': y -= (ph + sh)/2
            if key == 'right-of': x += (pw + sw)/2
            if key == 'left-of': x -= (pw + sw)/2
        offset = cfg.get('offset', [0, 0])
        if not isinstance(offset, list) or len(offset) != 2 or any(type(v) not in (int, float) for v in offset):
            raise ValueError(f'{name}: offset must be [x, y]')
        centers[name] = (x + offset[0]*sx, y + offset[1]*sy)
        visiting.remove(name)
        return centers[name]

    for name in COMPONENTS:
        if settings[name]['enabled']:
            center(name)
    def geometry(name):
        x, y = centers[name]
        return {'position': f'{round(x-w/2)}, {round(h/2-y)}', 'halign': 'center', 'valign': 'center'}
    def label(name, text, font_size, color, **extra):
        return block('label', monitor='', text=text, color=color,
                     font_size=round(font_size * sy), font_family=font,
                     **geometry(name), zindex=3, **extra)
    def overlay(name, text, font_size, color, dx=0, dy=0, **extra):
        x, y = centers[name]
        pos = f'{round(x-w/2+dx*sx)}, {round(h/2-y-dy*sy)}'
        return block('label', monitor='', text=text, color=color,
                     font_size=round(font_size*sy), font_family=font,
                     position=pos, halign='center', valign='center', zindex=3, **extra)
    def shape(name, color, radius=18):
        ww, hh = sizes[name]
        return block('shape', monitor='', size=f'{ww}, {hh}', color=color,
                     rounding=round(radius*sy), **geometry(name), zindex=1)
    def cmd(arg):
        return 'cmd[update:30000] python3 ' + str(ROOT / 'widget.py') + ' ' + arg

    font = settings['appearance'].get('font', 'Fira Sans')
    fg = color(settings['appearance'].get('foreground', '#f7f3ee'))
    muted = color(settings['appearance'].get('muted', '#dfd8d4'))
    accent = color(settings['appearance'].get('accent', '#eab8a4'))
    if not wallpaper.is_file():
        raise ValueError('wallpaper missing: ' + str(wallpaper))
    appearance = settings['appearance']
    blur_passes = appearance.get('blur_passes', 3)
    blur_size = appearance.get('blur_size', 7)
    brightness = appearance.get('brightness', 0.60)
    if type(blur_passes) is not int or not 0 <= blur_passes <= 10:
        raise ValueError('appearance.blur_passes must be an integer from 0 to 10')
    if type(blur_size) is not int or not 1 <= blur_size <= 20:
        raise ValueError('appearance.blur_size must be an integer from 1 to 20')
    if type(brightness) not in (int, float) or not 0.2 <= brightness <= 1:
        raise ValueError('appearance.brightness must be between 0.2 and 1')
    result = ['# Generated by lockscreen/render.py; edit settings.toml instead.\n',
              block('general', ignore_empty_input='true', hide_cursor='true'),
              block('background', monitor='', path=str(wallpaper), blur_passes=blur_passes,
                    blur_size=blur_size, brightness=brightness, contrast=0.90, zindex=-1)]
    if settings['clock']['enabled']:
        result.append(label('clock', 'cmd[update:1000] date +%H:%M', 74, fg))
    if settings['date']['enabled']:
        result.append(label('date', 'cmd[update:60000] date +"%A, %d %B %Y"', 19, muted))
    if settings['avatar']['enabled']:
        avatar = settings['avatar']
        image = os.path.expanduser(avatar.get('image', ''))
        if image:
            result.append(block('image', monitor='', path=prepare_avatar(image),
                                size=round(sizes['avatar'][0]), rounding=-1,
                                border_size=2, border_color=accent, **geometry('avatar'), zindex=2))
        else:
            result.append(shape('avatar', 'rgba(18191dcc)', radius=100))
            result.append(label('avatar', quote(avatar.get('initials', 'MA')), 62, fg))
    if settings['greeting']['enabled']:
        result.append(label('greeting', quote('Halo, ' + settings['greeting'].get('name', 'Aziz')), 17, fg))
    if settings['password']['enabled']:
        pw, ph = sizes['password']
        result.append(block('input-field', monitor='', size=f'{pw}, {ph}',
                            rounding=round(15*sy), outline_thickness=2,
                            outer_color=accent, inner_color='rgba(111015ee)',
                            font_color=fg, dots_center='true', fade_on_empty='false',
                            placeholder_text=quote('Masukkan password'),
                            fail_color='rgba(e87272ff)', **geometry('password'), zindex=2))
    if settings['music']['enabled']:
        result.append(shape('music', 'rgba(221c20ed)', 22))
        mx, my = centers['music']
        cover_pos = f'{round(mx-w/2-111*sx)}, {round(h/2-my)}'
        result.append(block('image', monitor='', path=str(Path.home() / '.cache/ml4w/lockscreen-cover.png'),
                            size=round(94*sy), rounding=round(13*sy),
                            reload_time=10, reload_cmd='python3 ' + str(ROOT / 'widget.py') + ' cover',
                            position=cover_pos, halign='center', valign='center', zindex=2))
        result.append(overlay('music', cmd('music'), 12, fg, dx=51, dy=-9))
        result.append(overlay('music', cmd('music-artist'), 10, muted, dx=51, dy=13))
        result.append(overlay('music', cmd('music-source'), 9, accent, dx=51, dy=-32))
        controls = [('control-previous', '◀', 0), ('control-play-pause', 'cmd[update:1000] python3 ' + str(ROOT / 'widget.py') + ' play-state', 51), ('control-next', '▶', 102)]
        for action, glyph, x in controls:
            bx = round(mx-w/2+x*sx)
            by = round(h/2-my-43*sy)
            onclick = 'python3 ' + str(ROOT / 'widget.py') + ' ' + action
            result.append(block('shape', monitor='', size=f'{round(35*sx)}, {round(27*sy)}',
                                color='rgba(ffffff23)', rounding=round(7*sy),
                                position=f'{bx}, {by}', halign='center', valign='center',
                                zindex=2, onclick=onclick))
            result.append(overlay('music', glyph, 14, fg, dx=x, dy=43, onclick=onclick))
    if settings['weather']['enabled']:
        result.append(shape('weather', 'rgba(f4eee5f2)', 17))
        result.append(overlay('weather', cmd('weather-icon'), 22, 'rgba(282225ff)', dx=-57))
        result.append(overlay('weather', cmd('weather'), 10, 'rgba(282225ff)', dx=16, dy=-12))
        result.append(overlay('weather', cmd('location'), 9, 'rgba(383035ff)', dx=16, dy=13))
    if settings['battery']['enabled']:
        result.append(shape('battery', 'rgba(9e4445f2)', 17))
        result.append(overlay('battery', cmd('battery-icon'), 22, 'rgba(ffffffff)', dx=-46))
        result.append(overlay('battery', cmd('battery'), 16, 'rgba(ffffffff)', dx=22))
    return '\n'.join(result)


def color(value):
    if not re.fullmatch('#[0-9a-fA-F]{6}', value):
        raise ValueError('colors must be #RRGGBB')
    return 'rgba(' + value[1:] + 'ff)'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='validate without modifying output')
    args = parser.parse_args()
    settings = tomllib.loads(SETTINGS.read_text())
    wallpaper_ref = Path(os.path.expanduser(settings['appearance']['wallpaper_file']))
    wallpaper = Path(wallpaper_ref.read_text().strip()).expanduser() if wallpaper_ref.is_file() else None
    if not wallpaper:
        raise ValueError('ML4W wallpaper pointer missing: ' + str(wallpaper_ref))
    text = render(settings, monitor_size(), wallpaper)
    if args.check:
        print('valid:', len(text), 'bytes; wallpaper:', wallpaper)
    else:
        tmp = OUTPUT.with_suffix('.conf.tmp')
        tmp.write_text(text)
        tmp.replace(OUTPUT)
        print('generated:', OUTPUT, '; wallpaper:', wallpaper)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, tomllib.TOMLDecodeError) as exc:
        print('lockscreen:', exc, file=sys.stderr)
        sys.exit(1)
