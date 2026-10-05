#!/usr/bin/env python3
"""Stitch NAV grid exports into a PNG without allocating the whole image."""
import argparse
import csv
import math
import os
from pathlib import Path
import struct
import sys
import zlib

try:
    from PIL import Image
except ImportError:
    raise SystemExit('Install Pillow first: py -m pip install Pillow  (or python -m pip install Pillow)')


def read_settings(path):
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def load_grid(folder):
    folder = Path(folder).resolve()
    m = read_settings(folder / 'map.txt')
    if m.get('format_version') != '1':
        raise ValueError('Expected a NAV capture folder with format_version=1.')
    cols, rows = int(m['columns']), int(m['rows'])
    pixels, border = int(m['tile_pixels']), int(m['border_pixels'])
    coverage, center_x, center_z = (float(m[k]) for k in ('tile_coverage_meters', 'center_x', 'center_z'))
    if not (1 <= cols <= 100 and 1 <= rows <= 100 and 1 <= pixels <= 8192 and 0 <= border <= 128):
        raise ValueError('Invalid dimensions in map.txt.')
    if not all(math.isfinite(v) for v in (coverage, center_x, center_z)) or coverage <= 0:
        raise ValueError('Invalid coverage or center in map.txt.')
    if m.get('image_top') != 'world_positive_z' or m.get('image_right') != 'world_positive_x':
        raise ValueError('Unrecognized tile orientation.')
    status_path = folder / 'status.txt'
    if status_path.exists():
        state = read_settings(status_path).get('state')
        if state != 'complete':
            raise ValueError(f'Capture status is {state!r}; wait for a complete capture before stitching.')
    tiles = {}
    with (folder / 'tiles.csv').open(newline='', encoding='utf-8-sig') as f:
        for tile in csv.DictReader(f):
            r, c = int(tile['row']), int(tile['column'])
            if not (0 <= r < rows and 0 <= c < cols) or (r, c) in tiles:
                raise ValueError(f'Duplicate or out-of-range grid cell: row {r}, column {c}.')
            name = tile['file']
            if not name or Path(name).name != name or '/' in name or '\\' in name:
                raise ValueError('Tile filenames must be plain filenames within the capture folder.')
            path = folder / name
            if not path.is_file():
                raise ValueError(f'Missing tile: {name}')
            expected_x = center_x + (c - (cols - 1) / 2) * coverage
            expected_z = center_z + ((rows - 1) / 2 - r) * coverage
            x, z = float(tile['center_x']), float(tile['center_z'])
            tolerance = max(0.001, coverage / pixels * 0.01)
            if not math.isfinite(x) or not math.isfinite(z) or abs(x - expected_x) > tolerance or abs(z - expected_z) > tolerance:
                raise ValueError(f'Tile coordinates disagree with the grid: {name}')
            tiles[r, c] = path
    if len(tiles) != rows * cols:
        raise ValueError(f'Grid is incomplete: {len(tiles)} of {rows * cols} tiles recorded.')
    # Inspect every header before opening an output file.
    size = pixels + 2 * border
    for path in tiles.values():
        with Image.open(path) as im:
            if im.format != 'PNG' or im.size != (size, size):
                raise ValueError(f'{path.name}: expected a {size} x {size} PNG; found {im.format} {im.size}.')
    return folder, m, rows, cols, pixels, border, tiles


def png_chunk(handle, kind, data):
    handle.write(struct.pack('>I', len(data)))
    handle.write(kind)
    handle.write(data)
    handle.write(struct.pack('>I', zlib.crc32(data, zlib.crc32(kind)) & 0xffffffff))


def stitch(folder, output=None):
    folder, meta, rows, cols, pixels, border, tiles = load_grid(folder)
    output = Path(output).resolve() if output else folder / 'stitched.png'
    if output in {p.resolve() for p in tiles.values()}:
        raise ValueError('Output cannot overwrite an input tile.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.partial')
    width, height = cols * pixels, rows * pixels
    # Hold one tile row as raw RGB, not an entire mosaic. At 20 x 2048 this is ~240 MiB.
    print(f'Stitching {cols} x {rows} tiles -> {width:,} x {height:,} pixels.', flush=True)
    print(f'Tile-row RGB buffer: approximately {cols * pixels * pixels * 3 / 1024**2:.0f} MiB.', flush=True)
    try:
        with temporary.open('wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')
            png_chunk(f, b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            compressor = zlib.compressobj(level=6)
            pending = bytearray()
            for r in range(rows):
                raw_tiles = []
                for c in range(cols):
                    with Image.open(tiles[r, c]) as im:
                        with im.crop((border, border, border + pixels, border + pixels)).convert('RGB') as crop:
                            raw_tiles.append(crop.tobytes())
                stride = pixels * 3
                for y in range(pixels):
                    offset = y * stride
                    # PNG filter 0 is lossless and needs no previous image rows.
                    scanline = b'\x00' + b''.join(tile[offset:offset + stride] for tile in raw_tiles)
                    pending.extend(compressor.compress(scanline))
                    if len(pending) >= 1024 * 1024:
                        png_chunk(f, b'IDAT', pending)
                        pending.clear()
                del raw_tiles
                print(f'Finished tile row {r + 1}/{rows}.', flush=True)
            pending.extend(compressor.flush())
            if pending:
                png_chunk(f, b'IDAT', pending)
            png_chunk(f, b'IEND', b'')
        os.replace(temporary, output)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    coverage = float(meta['tile_coverage_meters'])
    meters_per_pixel = coverage / pixels
    center_x, center_z = float(meta['center_x']), float(meta['center_z'])
    # PNG world file: x scale, rotations, negative z scale, top-left pixel CENTER.
    # These are VTOL global coordinates.
    world = output.with_suffix('.pgw')
    world.write_text('\n'.join(format(v, '.17g') for v in (
        meters_per_pixel, 0, 0, -meters_per_pixel,
        center_x - cols * coverage / 2 + meters_per_pixel / 2,
        center_z + rows * coverage / 2 - meters_per_pixel / 2)) + '\n', encoding='ascii')
    print(f'Saved: {output}\nVTOL coordinate world file: {world}', flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path, help='Capture folder containing map.txt and tiles.csv')
    parser.add_argument('--output', type=Path, help='Output PNG (default: capture-folder/stitched.png)')
    args = parser.parse_args()
    try:
        stitch(args.folder, args.output)
    except (OSError, ValueError, KeyError, csv.Error) as ex:
        parser.exit(1, f'Could not stitch map: {ex}\n')


if __name__ == '__main__':
    main()
