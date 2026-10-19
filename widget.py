#!/usr/bin/env python3
"""Lockscreen widgets: live MPRIS cover/text, weather and battery state."""
import json
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import time
import tomllib
import urllib.request
from urllib.parse import quote, unquote, urlparse
from PIL import Image, ImageDraw

ROOT = Path.home() / '.config/hypr/lockscreen'
CACHE = Path.home() / '.cache/ml4w/lockscreen-weather.json'
COVER = Path.home() / '.cache/ml4w/lockscreen-cover.png'
COVER_META = Path.home() / '.cache/ml4w/lockscreen-cover-url'


def run(argv):
    try:
        return subprocess.check_output(argv, stderr=subprocess.DEVNULL, timeout=2, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def clean(text, limit=32):
    return ''.join(c if c.isprintable() and c not in '<>&' else ' ' for c in text).strip()[:limit]


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ML4W-lockscreen/1.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


def weather():
    city = tomllib.loads((ROOT / 'settings.toml').read_text())['weather'].get('city', 'auto')
    key = str(city)
    try:
        saved = json.loads(CACHE.read_text())
        if saved.get('key') == key and 'code' in saved and time.time() - saved['time'] < 1800:
            return saved
    except (OSError, ValueError, KeyError):
        saved = {}
    try:
        if city == 'auto':
            geo = fetch('https://ipwho.is/')
            if not geo.get('success'):
                raise ValueError('IP location unavailable')
            lat, lon = geo['latitude'], geo['longitude']
            location = geo.get('city') or geo.get('region') or 'Lokasi'
        else:
            geo = fetch('https://geocoding-api.open-meteo.com/v1/search?name=' + quote(city) + '&count=1')
            result = geo['results'][0]
            lat, lon, location = result['latitude'], result['longitude'], result['name']
        current = fetch(f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto')['current']
        code = current['weather_code']
        condition = ('Cerah' if code <= 1 else 'Berawan' if code <= 3 else
                     'Hujan' if code in (51, 53, 55, 61, 63, 65, 80, 81, 82) else
                     'Badai' if code >= 95 else 'Berkabut')
        saved = {'key': key, 'time': time.time(), 'location': clean(location, 22), 'code': code,
                 'weather': f"{condition} · {round(current['temperature_2m'])}°C"}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(saved))
        return saved
    except (OSError, ValueError, KeyError, IndexError, TimeoutError):
        if saved.get('key') == key and saved.get('weather'):
            return saved
        return {'weather': 'Cuaca offline', 'location': 'Cek koneksi', 'code': -1}


def weather_icon():
    code = weather().get('code', -1)
    if code < 0: return '○'
    if code <= 1: return '☀'
    if code <= 3: return '☁'
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82): return '☂'
    if code >= 95: return 'ϟ'
    return '≋'


def battery_state():
    for root in sorted(Path('/sys/class/power_supply').glob('BAT*')):
        try:
            return int((root / 'capacity').read_text()), (root / 'status').read_text().strip()
        except (OSError, ValueError):
            pass
    return None, None


def battery():
    pct, status = battery_state()
    return f"{'+' if status in ('Charging', 'Full') else ''}{pct}%" if pct is not None else 'Tanpa baterai'


def battery_icon():
    pct, status = battery_state()
    if pct is None: return '○'
    if status == 'Charging': return 'ϟ'
    return '▰' if pct >= 60 else '▣' if pct >= 25 else '▱'


def current_player():
    for player in run(['playerctl', '-l']).splitlines():
        if run(['playerctl', '-p', player, 'status']) == 'Playing':
            return player
    return None


def controllable_player():
    return current_player() or next(iter(run(['playerctl', '-l']).splitlines()), None)


def control(action):
    player = controllable_player()
    commands = {'control-previous': 'previous', 'control-play-pause': 'play-pause',
                'control-next': 'next'}
    if not player or action not in commands:
        return False
    try:
        return subprocess.run(['playerctl', '-p', player, commands[action]],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=3).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def play_state():
    player = controllable_player()
    return 'Ⅱ' if player and run(['playerctl', '-p', player, 'status']) == 'Playing' else '▶'


def fallback_cover():
    canvas = Image.new('RGB', (160, 160), '#383033')
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((24, 24, 136, 136), outline='#eab8a4', width=2)
    draw.ellipse((40, 99, 65, 118), fill='#eab8a4')
    draw.line((63, 107, 63, 56, 111, 44, 111, 96), fill='#eab8a4', width=8, joint='curve')
    draw.ellipse((90, 87, 115, 106), fill='#eab8a4')
    return canvas


def cover():
    player = current_player()
    url = run(['playerctl', '-p', player, 'metadata', '--format', '{{mpris:artUrl}}']) if player else ''
    previous = COVER_META.read_text() if COVER_META.is_file() else None
    if url == previous and COVER.is_file():
        return COVER
    image = None
    parsed = urlparse(url)
    try:
        if parsed.scheme == 'https' and parsed.hostname == 'i.scdn.co':
            req = urllib.request.Request(url, headers={'User-Agent': 'ML4W-lockscreen/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = response.read(5_000_001)
            if len(data) > 5_000_000: raise ValueError('cover too large')
            image = Image.open(BytesIO(data))
        elif parsed.scheme == 'file':
            image = Image.open(unquote(parsed.path))
        if image is None: image = fallback_cover()
        image.thumbnail((240, 240))
        image = image.convert('RGB').resize((160, 160))
        COVER.parent.mkdir(parents=True, exist_ok=True)
        temp = COVER.with_suffix('.tmp.png')
        image.save(temp, format='PNG')
        temp.replace(COVER)
        COVER_META.write_text(url)
    except (OSError, ValueError, TimeoutError):
        if not COVER.is_file():
            COVER.parent.mkdir(parents=True, exist_ok=True)
            fallback_cover().save(COVER)
    return COVER


def music(kind):
    player = current_player()
    if player:
        fmt = {'music': '{{title}}', 'music-artist': '{{artist}}', 'music-source': '{{playerName}}'}[kind]
        return clean(run(['playerctl', '-p', player, 'metadata', '--format', fmt]), 22) or 'Musik'
    return {'music': 'Tidak ada musik', 'music-artist': 'Putar musik', 'music-source': 'MEDIA'}[kind]


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else ''
    if kind in ('control-previous', 'control-play-pause', 'control-next'):
        if not control(kind): raise SystemExit(1)
    elif kind == 'play-state': print(play_state())
    elif kind == 'cover': print(cover())
    elif kind == 'weather-icon': print(weather_icon())
    elif kind == 'battery-icon': print(battery_icon())
    elif kind in ('weather', 'location'): print(weather()[kind])
    elif kind == 'battery': print(battery())
    elif kind in ('music', 'music-artist', 'music-source'): print(music(kind))
    else: raise SystemExit('unknown widget')


if __name__ == '__main__':
    main()
