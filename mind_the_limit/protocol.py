"""Encodes messages for the Divoom Timebox Evo.

Follows the protocol description by Jérôme Wiedemann (RomRider/node-divoom-timebox-evo,
PROTOCOL.md, MIT License): every message is

    01 | length (2 bytes, LSB first) | command | data | checksum (2 bytes, LSB first) | 02

where the length counts command, data and checksum, and the checksum is the sum of the length
bytes, the command and the data. The Timebox Evo needs no byte escaping.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

BRIGHTNESS = 0x74
IMAGE = 0x44
STATE = 0x46


def frame(command: int, data: bytes = b"") -> bytes:
    data = bytes(data)
    length = 1 + len(data) + 2
    body = bytes((length & 0xFF, length >> 8 & 0xFF, command)) + data
    checksum = sum(body) & 0xFFFF
    return b"\x01" + body + bytes((checksum & 0xFF, checksum >> 8)) + b"\x02"


def brightness(level: int) -> bytes:
    """0 = dark, 100 = full brightness."""
    return frame(BRIGHTNESS, [max(0, min(100, int(level)))])


def state_request() -> bytes:
    """Asks the box for its settings. It changes nothing, so it doubles as a keep-alive."""
    return frame(STATE)


def quiet() -> bytes:
    """Switches off the box's own auto-play, so the panel stays on screen."""
    return frame(0x26, [0x00]) + frame(0x40, [0x00] * 10)


def _pixel_data(indices: Sequence[int], bits: int) -> bytes:
    # Each index contributes its lowest `bits` bits, least significant first; the bit stream is
    # cut into bytes, again least significant bit first (PROTOCOL.md, "Pixel String").
    out, acc, filled = bytearray(), 0, 0
    for index in indices:
        for i in range(bits):
            acc |= (index >> i & 1) << filled
            filled += 1
            if filled == 8:
                out.append(acc)
                acc, filled = 0, 0
    if filled:
        out.append(acc)
    return bytes(out)


def image(pixels: Sequence[int]) -> bytes:
    """A still 16 x 16 image from 256 RGB integers (0xRRGGBB), row by row from the top left."""
    if len(pixels) != 256:
        raise ValueError("an image has exactly 256 pixels, got %d" % len(pixels))
    palette: Dict[int, int] = {}
    indices: List[int] = []
    for color in pixels:
        indices.append(palette.setdefault(int(color) & 0xFFFFFF, len(palette)))
    count = len(palette)
    bits = max(1, (count - 1).bit_length())
    colors = b"".join(c.to_bytes(3, "big") for c in palette)
    image_data = bytes((count % 256,)) + colors + _pixel_data(indices, bits)
    size = 6 + len(image_data)           # AA, the size itself, 000000, then the image data
    header = bytes((0x00, 0x0A, 0x0A, 0x04, 0xAA, size & 0xFF, size >> 8, 0x00, 0x00, 0x00))
    return frame(IMAGE, header + image_data)


def is_reply(data: bytes) -> bool:
    """True for an answer from the box, false for anything else on the line.

    The box answers in binary. A wrong RFCOMM channel (the audio profile) answers with text
    such as `AT+BRSF=63`, which can contain the byte 0x46 too, but never a byte >= 0x80."""
    return bool(data) and STATE in data and any(b >= 0x80 for b in data)
