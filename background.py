"""Reference-calibrated background, only for the matching original wallpaper."""
import hashlib
from pathlib import Path

ORIGINAL_SHA256 = 'abef4dd338129d108a3c89908f595d4bcd7b4e128c03e50a4b26ca7b1d8ea144'
ASSET = Path(__file__).parent / 'assets/reference-wallpaper.png'


def resolve(wallpaper):
    wallpaper = Path(wallpaper)
    if ASSET.is_file() and hashlib.sha256(wallpaper.read_bytes()).hexdigest() == ORIGINAL_SHA256:
        return ASSET, True
    return wallpaper, False
