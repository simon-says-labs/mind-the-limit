"""Draws the 16 x 16 panel: one row per limit, the percentage on the left and an 8-pixel bar on the right.

Pixels are a flat list of 256 RGB integers (0xRRGGBB), row by row from the top left.
`to_png` writes the same pixels as an image, so the panel can be checked without a device.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Sequence

SIZE = 16
OFF = 0x000000
TRACK = 0x303030          # the empty part of a bar, glowing faintly
ERROR_COLOR = 0xE5484D

# The colour replaces a label: white = session, orange = week, violet = the model's own week.
DEFAULT_COLORS: Dict[str, int] = {"session": 0xFFFFFF, "week": 0xE8824A, "model": 0xA877E8, "other": 0x4AA3E8}

# 3 x 5 pixel font, the same style the box uses for its own clock.
FONT = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "011", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "?": ("111", "001", "011", "000", "010"),
    "C": ("111", "100", "100", "100", "111"),
}

ROWS = (0, 5, 10)         # top line of each meter row
ERROR_SYMBOLS = {"usage": "?", "claude": "C"}


def _draw(grid: List[int], x0: int, y0: int, text: str, color: int, scale: int = 1) -> None:
    for i, ch in enumerate(text):
        for r, line in enumerate(FONT[ch]):
            for c, bit in enumerate(line):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        x, y = x0 + (i * 4 + c) * scale + dx, y0 + r * scale + dy
                        if 0 <= x < SIZE and 0 <= y < SIZE:
                            grid[y * SIZE + x] = color


def render(meters: Sequence, colors: Optional[Dict[str, int]] = None) -> List[int]:
    """Up to three meters (session, week, model week); further ones are left out."""
    palette = dict(DEFAULT_COLORS, **(colors or {}))
    grid = [OFF] * (SIZE * SIZE)
    for y0, meter in zip(ROWS, meters):
        color = palette.get(meter.kind, palette["other"])
        shown = max(0, min(99, int(round(meter.percent))))
        _draw(grid, 0, y0, "%02d" % shown, color)
        fill = max(0, min(8, int(round(meter.percent / 100 * 8))))
        for y in range(y0 + 1, y0 + 4):
            for x in range(8):
                grid[y * SIZE + 8 + x] = color if x < fill else TRACK
    return grid


def render_error(code: str) -> List[int]:
    """A large red symbol: `?` = the limits could not be read, `C` = the claude command is missing."""
    grid = [OFF] * (SIZE * SIZE)
    _draw(grid, 5, 3, ERROR_SYMBOLS.get(code, "?"), ERROR_COLOR, scale=2)
    return grid


def to_png(pixels: Sequence[int], path, scale: int = 20, gap: int = 2, background: int = 0x101010,
           unlit: int = 0x1C1C1C) -> Path:
    """Writes the panel as a PNG that looks like the LED matrix (square dots with a gap)."""
    side = SIZE * scale
    rows = []
    for y in range(side):
        py, iy = divmod(y, scale)
        row = bytearray(b"\x00")
        for x in range(side):
            px, ix = divmod(x, scale)
            if iy < gap // 2 or iy >= scale - (gap - gap // 2) or ix < gap // 2 or ix >= scale - (gap - gap // 2):
                color = background
            else:
                color = pixels[py * SIZE + px] or unlit
            row += bytes(((color >> 16) & 255, (color >> 8) & 255, color & 255))
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
           + chunk(b"IEND", b""))
    path = Path(path)
    path.write_bytes(png)
    return path
