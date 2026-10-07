import random
import unittest

from mind_the_limit import protocol


def unframe(data):
    """Checks start, end, length and checksum as PROTOCOL.md describes them; returns cmd + data."""
    assert data[0] == 0x01 and data[-1] == 0x02, data.hex()
    length = data[1] | data[2] << 8
    body = data[3:-3]
    assert length == len(body) + 2, (length, len(body))
    checksum = data[-3] | data[-2] << 8
    assert checksum == sum(data[1:-3]) & 0xFFFF
    return body


def unpack_pixels(raw, bits):
    stream = []
    for byte in raw:
        stream.extend((byte >> i) & 1 for i in range(8))
    return [sum(stream[p * bits + i] << i for i in range(bits)) for p in range(256)]


class FrameTest(unittest.TestCase):
    def test_brightness_by_hand(self):
        # 01, length 4 (74 + 32 + 2 checksum bytes) LSB first, 74 32, checksum 04+00+74+32 = AA LSB first, 02
        self.assertEqual(protocol.brightness(50).hex(), "010400743" "2aa0002")

    def test_brightness_is_clamped(self):
        self.assertEqual(unframe(protocol.brightness(140)), bytes([0x74, 100]))
        self.assertEqual(unframe(protocol.brightness(-5)), bytes([0x74, 0]))

    def test_state_request(self):
        self.assertEqual(unframe(protocol.state_request()), bytes([0x46]))

    def test_quiet_is_two_frames(self):
        data = protocol.quiet()
        first_len = 3 + (data[1] | data[2] << 8) + 1
        self.assertEqual(unframe(data[:first_len]), bytes([0x26, 0x00]))
        self.assertEqual(unframe(data[first_len:]), bytes([0x40]) + bytes(10))

    def test_checksum_wraps_at_16_bits(self):
        data = protocol.frame(0x44, bytes([0xFF] * 400))
        unframe(data)


class ImageTest(unittest.TestCase):
    def check(self, pixels):
        body = unframe(protocol.image(pixels))
        self.assertEqual(body[:6], bytes([0x44, 0x00, 0x0A, 0x0A, 0x04, 0xAA]))
        size = body[6] | body[7] << 8
        self.assertEqual(body[8:11], bytes(3))
        self.assertEqual(size, len(body) - 5, "size counts AA, the size itself, 000000 and the image data")
        count = body[11] or 256
        palette = [int.from_bytes(body[12 + 3 * i:15 + 3 * i], "big") for i in range(count)]
        bits = max(1, (count - 1).bit_length())
        indices = unpack_pixels(body[12 + 3 * count:], bits)
        self.assertEqual(len(body[12 + 3 * count:]), 256 * bits // 8)
        self.assertEqual([palette[i] for i in indices], list(pixels))

    def test_one_colour(self):
        self.check([0x000000] * 256)

    def test_two_colours(self):
        self.check([0xFFFFFF if i % 3 else 0x000000 for i in range(256)])

    def test_panel_colours(self):
        self.check([[0, 0xFFFFFF, 0xE8824A, 0xA877E8, 0x303030][i % 5] for i in range(256)])

    def test_random_images(self):
        rng = random.Random(7)
        for colours in (3, 4, 5, 17, 100, 256):
            palette = [rng.randrange(1 << 24) for _ in range(colours)]
            pixels = palette + [rng.choice(palette) for _ in range(256 - colours)]
            self.check(pixels)

    def test_wrong_size(self):
        with self.assertRaises(ValueError):
            protocol.image([0] * 255)


class ReplyTest(unittest.TestCase):
    def test_binary_reply_with_command_byte(self):
        self.assertTrue(protocol.is_reply(bytes([0x01, 0x10, 0x00, 0x04, 0x46, 0x55, 0x80, 0x02])))

    def test_at_command_from_the_audio_channel_is_not_a_reply(self):
        self.assertFalse(protocol.is_reply(b"AT+BRSF=63\r"))

    def test_empty(self):
        self.assertFalse(protocol.is_reply(b""))


if __name__ == "__main__":
    unittest.main()
