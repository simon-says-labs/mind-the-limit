import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from mind_the_limit import panel
from mind_the_limit.usage import Meter

SESSION, WEEK, MODEL = Meter("session", "session", 15), Meter("week", "all models", 34), Meter("model", "Fable", 0)
SYMBOLS = {"W": 0xFFFFFF, "O": 0xE8824A, "V": 0xA877E8, "t": 0x303030, ".": 0x000000, "R": panel.ERROR_COLOR}

# The panel Simon chose on 2026-08-02 (variant C), drawn by the original script for 15 / 34 / 0.
EXPECTED_15_34_0 = [
    ".W..WWW.........",
    "WW..W...Wttttttt",
    ".W..WWW.Wttttttt",
    ".W....W.Wttttttt",
    "WWW.WWW.........",
    "OOO.O.O.........",
    "..O.O.O.OOOttttt",
    ".OO.OOO.OOOttttt",
    "..O...O.OOOttttt",
    "OOO...O.........",
    "VVV.VVV.........",
    "V.V.V.V.tttttttt",
    "V.V.V.V.tttttttt",
    "V.V.V.V.tttttttt",
    "VVV.VVV.........",
    "................",
]


def art(pixels):
    names = {v: k for k, v in SYMBOLS.items()}
    return ["".join(names.get(pixels[y * 16 + x], "?") for x in range(16)) for y in range(16)]


class RenderTest(unittest.TestCase):
    def test_matches_the_original_panel(self):
        self.assertEqual(art(panel.render([SESSION, WEEK, MODEL])), EXPECTED_15_34_0)

    def test_always_256_pixels(self):
        for meters in ([], [SESSION], [SESSION, WEEK, MODEL, Meter("model", "Opus", 50)]):
            self.assertEqual(len(panel.render(meters)), 256)

    def test_fourth_meter_is_left_out(self):
        four = panel.render([SESSION, WEEK, MODEL, Meter("model", "Opus", 88)])
        self.assertEqual(four, panel.render([SESSION, WEEK, MODEL]))

    def test_single_meter_uses_the_top_row_only(self):
        rows = art(panel.render([SESSION]))
        self.assertEqual(rows[:5], EXPECTED_15_34_0[:5])
        self.assertTrue(all(set(r) == {"."} for r in rows[5:]))

    def test_values_above_99_show_99_and_a_full_bar(self):
        rows = art(panel.render([Meter("session", "session", 104.6)]))
        self.assertEqual(rows[1][8:], "WWWWWWWW")
        self.assertEqual(rows[0][:7], "WWW.WWW")

    def test_negative_or_fraction(self):
        rows = art(panel.render([Meter("session", "session", -3), Meter("week", "all models", 49.5)]))
        self.assertEqual(rows[1][8:], "tttttttt")
        self.assertEqual(rows[6][8:], "OOOOtttt")

    def test_colours_can_be_changed(self):
        pixels = panel.render([SESSION], colors={"session": 0x00FF00})
        self.assertIn(0x00FF00, pixels)
        self.assertNotIn(0xFFFFFF, pixels)


class ErrorImageTest(unittest.TestCase):
    def test_error_images_differ_from_every_valid_panel(self):
        for code in ("usage", "claude"):
            pixels = panel.render_error(code)
            self.assertEqual(len(pixels), 256)
            self.assertIn(panel.ERROR_COLOR, pixels)
            self.assertNotIn(panel.TRACK, pixels)

    def test_two_errors_look_different(self):
        self.assertNotEqual(panel.render_error("usage"), panel.render_error("claude"))


class PngTest(unittest.TestCase):
    def test_png_is_valid_and_scaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.png"
            panel.to_png(panel.render([SESSION, WEEK, MODEL]), path, scale=20)
            data = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (320, 320))
        idat = data[data.index(b"IDAT") + 4:]
        length = struct.unpack(">I", data[data.index(b"IDAT") - 4:data.index(b"IDAT")])[0]
        raw = zlib.decompress(idat[:length])
        self.assertEqual(len(raw), 320 * (1 + 320 * 3))


if __name__ == "__main__":
    unittest.main()
