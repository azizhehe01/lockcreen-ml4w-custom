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
import artwork

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
    # Hyprlang values are not JSON strings: literal quotes need no backslashes.
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('#', '＃')


def prepare_avatar(source):
    target = Path.home() / '.cache/ml4w/lockscreen-avatar.png'
    if not Path(source).is_file():
        raise ValueError('avatar image missing: ' + source)
    try:
        with Image.open(source) as image:
            image = image.convert('RGB')
            image.thumbnail((400, 400))
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f'.{target.stem}-{os.getpid()}.tmp.png')
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


def render(settings, dims, wallpaper, initial_images=None):
    presets = {'big': 1.0, 'medium': 0.8, 'small': 0.65}
    preset = settings.get('widgets', {}).get('size', 'big')
    if not isinstance(preset, str) or preset not in presets:
        raise ValueError('widgets.size must be big, medium, or small')
    widget_scale = presets[preset]
    def scale(name):
        return widget_scale if name in ('music', 'weather', 'battery') else 1.0
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
        sizes[name] = (round(size[0]*sx*scale(name)), round(size[1]*sy*scale(name)))

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
        offset_scale = scale(name) if key != 'anchor' else 1.0
        centers[name] = (x + offset[0]*sx*offset_scale, y + offset[1]*sy*offset_scale)
        visiting.remove(name)
        return centers[name]

    for name in COMPONENTS:
        if settings[name]['enabled']:
            center(name)
    def geometry(name):
        x, y = centers[name]
        return {'position': f'{round(x-w/2)}, {round(h/2-y)}', 'halign': 'center', 'valign': 'center'}
    def label(name, text, font_size, color, family=None, **extra):
        return block('label', monitor='', text=text, color=color,
                     font_size=round(font_size * sy), font_family=family or font,
                     **geometry(name), zindex=3, **extra)
    def overlay(name, text, font_size, color, dx=0, dy=0, **extra):
        x, y = centers[name]
        pos = f'{round(x-w/2+dx*sx)}, {round(h/2-y-dy*sy)}'
        return block('label', monitor='', text=text, color=color,
                     font_size=round(font_size*sy), font_family=font,
                     position=pos, halign='center', valign='center', zindex=3, **extra)
    def left_text(name, text, font_size, color, dx, dy):
        font_size, dx, dy = (v*scale(name) for v in (font_size, dx, dy))
        x, y = centers[name]
        return block('label', monitor='', text=text, color=color,
                     font_size=round(font_size*sy), font_family=font,
                     position=f'{round(x+dx*sx)}, {round(h/2-y-dy*sy)}',
                     halign='left', valign='center', zindex=3)
    def shape(name, color, radius=18):
        ww, hh = sizes[name]
        return block('shape', monitor='', size=f'{ww}, {hh}', color=color,
                     rounding=round(radius*sy), **geometry(name), zindex=1)
    def cmd(arg):
        interval = 2000 if arg.startswith('music') else 30000
        return f'cmd[update:{interval}] python3 ' + str(ROOT / 'widget.py') + ' ' + arg

    font = settings['appearance'].get('font', 'Fira Sans')
    fg = color(settings['appearance'].get('foreground', '#f7f3ee'))
    muted = color(settings['appearance'].get('muted', '#dfd8d4'))
    accent = color(settings['appearance'].get('accent', '#f5c6a7'))
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
    import background
    wallpaper, prepared = background.resolve(wallpaper)
    if prepared:
        blur_passes, brightness = 0, 1.0
    result = ['# Generated by lockscreen/render.py; edit settings.toml instead.\n',
              block('general', ignore_empty_input='true', hide_cursor='true'),
              block('background', monitor='', path=str(wallpaper), blur_passes=blur_passes,
                    blur_size=blur_size, brightness=brightness, contrast=1.0, zindex=-1)]
    if settings['clock']['enabled']:
        # Calibrated against the isolated native 1920x1080 compositor capture.
        result.append(label('clock', 'cmd[update:1000] date +%H:%M', 77, fg, family='Fira Sans'))
    if settings['date']['enabled']:
        result.append(label('date', 'cmd[update:60000] date +"%A, %d %B %Y"', 20, muted, family='Source Code Pro'))
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
        result.append(label('greeting', quote('"Halo, ' + settings['greeting'].get('name', 'Aziz') + '"'), 20, fg, family='Source Code Pro'))
    if settings['password']['enabled']:
        pw, ph = sizes['password']
        result.append(block('input-field', monitor='', size=f'{pw}, {ph}',
                            rounding=0, outline_thickness=0,
                            outer_color='rgba(00000000)', inner_color='rgba(00000000)',
                            font_family=font,
                            font_color=fg, dots_center='true', fade_on_empty='false',
                            placeholder_text='', dots_size=0.20, dots_spacing=0.35,
                            # Zero outline makes state accents paint the inner box.
                            # Keep every state transparent, without hiding dots/errors.
                            check_color='rgba(00000000)', fail_color='rgba(00000000)',
                            capslock_color='rgba(00000000)', numlock_color='rgba(00000000)',
                            bothlock_color='rgba(00000000)', swap_font_color='false',
                            **geometry('password'), zindex=2))
    def panel(name, radius=24):
        # A single RGBA surface: never put opaque peach under a translucent fill.
        image = artwork.panel(sizes[name], round(radius*sy*scale(name)), appearance.get('accent', '#f5c6a7'))
        return [block('image', monitor='', path=artwork.save(image, 'panel-'+name),
                      size=min(sizes[name]), rounding=0, border_size=0,
                      **geometry(name), zindex=1)]

    def picture(name, path, width, dx=0, dy=0, refresh=None, interval=1, **extra):
        width, dx, dy = (v*scale(name) for v in (width, dx, dy))
        x, y = centers[name]
        if Path(path).is_file():
            with Image.open(path) as source:
                native_size = round(width*sx*min(source.size)/source.width)
        else:
            native_size = round(width*sx)  # cover is square and can load asynchronously
        values = dict(monitor='', path=path, size=native_size, rounding=0,
                      border_size=0, position=f'{round(x-w/2+dx*sx)}, {round(h/2-y-dy*sy)}',
                      halign='center', valign='center', zindex=3)
        if refresh:
            values.update(reload_time=interval, reload_cmd='python3 '+str(ROOT/'widget.py')+' '+refresh)
        values.update(extra)
        return block('image', **values)

    def live_image(name, kind, width, dx, dy, interval=1, **extra):
        # Startup has a truthful empty/unknown image; reload_cmd reads real state.
        if 'progress' in kind or 'bar' in kind:
            initial = artwork.progress((300,7) if 'music' in kind else (102,7), None, '#f5c6a7')
        else:
            initial = artwork.icon('play' if kind == 'play-image' else 'offline')
        path = (initial_images or {}).get(kind) or artwork.save(initial, kind)
        return picture(name, path, width, dx, dy, kind, interval, **extra)

    if settings['music']['enabled']:
        import music_background
        result.append(picture('music', music_background.current(), 498,
                              refresh='music-background-image', interval=5, zindex=1))
        result.append(left_text('music', cmd('music-source'), 11, muted, -216, 78))
        result.append(left_text('music', cmd('music'), 17, fg, -216, 105))
        result.append(left_text('music', cmd('music-artist'), 14, muted, -216, 132))
        result.append(live_image('music', 'music-progress-image', 420, 0, 163))
        for action, symbol, x in [('control-previous','previous',-110), ('control-play-pause','play',0), ('control-next','next',110)]:
            onclick = 'python3 '+str(ROOT/'widget.py')+' '+action
            if symbol == 'play':
                result.append(live_image('music','play-image',54,x,205,onclick=onclick))
            else:
                result.append(picture('music',artwork.save(artwork.icon(symbol),symbol),54,x,205,onclick=onclick))
    if settings['weather']['enabled']:
        result.extend(panel('weather'))
        result.append(live_image('weather','weather-image',64,-66,-10,30))
        result.append(left_text('weather', cmd('weather-temp'), 28, fg, -10, -24))
        result.append(left_text('weather', cmd('weather-condition'), 14, muted, -10, 10))
        result.append(left_text('weather', cmd('location'), 14, muted, -10, 35))
    if settings['battery']['enabled']:
        result.extend(panel('battery'))
        result.append(live_image('battery','battery-image',76,-66,-4,30))
        result.append(left_text('battery', cmd('battery'), 28, fg, -10, -24))
        result.append(left_text('battery', cmd('battery-status'), 13, muted, -10, 12))
        result.append(live_image('battery','battery-bar-image',102,41,38,30))
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
    initial_images = {}
    if not args.check:
        import widget
        for component, kinds in {'music': ('music-progress-image','play-image'),
                                 'weather': ('weather-image',),
                                 'battery': ('battery-image','battery-bar-image')}.items():
            if settings[component]['enabled']:
                for kind in kinds:
                    initial_images[kind] = widget.image_widget(kind)
    text = render(settings, monitor_size(), wallpaper, initial_images)
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
