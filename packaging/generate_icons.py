#!/usr/bin/env python3
"""
Regenerate desktop/app icons from static/favicon.svg.

Requires: pip install cairosvg pillow

Produces:
  static/weblint.png          (Linux window / fallback, 256px)
  static/weblint.ico          (Windows exe + window)
  static/weblint.icns         (macOS app bundle)
  static/icons/weblint-*.png  (per-size Linux theme icons)
"""
from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static'
SVG = (STATIC / 'favicon.svg').read_bytes()


def render_mark(size: int) -> Image.Image:
    data = cairosvg.svg2png(bytestring=SVG, output_width=size, output_height=size)
    return Image.open(BytesIO(data)).convert('RGBA')


def make_icon(size: int) -> Image.Image:
    """Composite the favicon mark onto a dark rounded square for title-bar clarity."""
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    pad = max(1, size // 32)
    radius = max(2, size // 6)
    draw.rounded_rectangle(
        [pad, pad, size - pad - 1, size - pad - 1],
        radius=radius,
        fill=(26, 29, 32, 255),
    )
    return Image.alpha_composite(canvas, render_mark(size))


def write_ico(images: dict[int, Image.Image], path: Path) -> None:
    order = [16, 24, 32, 48, 64, 128, 256]
    blobs = []
    for size in order:
        buf = BytesIO()
        images[size].save(buf, format='PNG')
        blobs.append((size, buf.getvalue()))

    count = len(blobs)
    offset = 6 + (16 * count)
    entries = []
    data_parts = []
    for size, blob in blobs:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        entries.append(struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(blob), offset))
        data_parts.append(blob)
        offset += len(blob)

    path.write_bytes(struct.pack('<HHH', 0, 1, count) + b''.join(entries) + b''.join(data_parts))


def write_icns(images: dict[int, Image.Image], path: Path) -> None:
    type_codes = {
        16: b'icp4',
        32: b'icp5',
        64: b'icp6',
        128: b'ic07',
        256: b'ic08',
        512: b'ic09',
    }
    entries = []
    for size, code in type_codes.items():
        buf = BytesIO()
        images[size].save(buf, format='PNG')
        data = buf.getvalue()
        entries.append(code + struct.pack('>I', len(data) + 8) + data)
    body = b''.join(entries)
    path.write_bytes(b'icns' + struct.pack('>I', len(body) + 8) + body)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    images = {size: make_icon(size) for size in sizes}
    images[256].save(STATIC / 'weblint.png')
    write_ico(images, STATIC / 'weblint.ico')
    write_icns(images, STATIC / 'weblint.icns')

    icon_dir = STATIC / 'icons'
    icon_dir.mkdir(exist_ok=True)
    for size in (16, 32, 48, 256):
        images[size].save(icon_dir / f'weblint-{size}.png')

    for name in ('weblint.png', 'weblint.ico', 'weblint.icns'):
        path = STATIC / name
        print(f'{path.relative_to(ROOT)} ({path.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
