import unittest
from PIL import Image, ImageChops

from sticker_library import draw_stickers


class StickerAnimationTests(unittest.TestCase):
    def test_sticker_changes_position_and_scale_during_entrance(self):
        scene = {"stickers": [{"id": "idea", "x": 0.5, "y": 0.4,
                               "size": 150, "start": 0.0, "end": 1.0,
                               "animation": "pop"}]}
        early = Image.new("RGB", (640, 360), "black")
        late = early.copy()
        draw_stickers(early, scene, 0.02)
        draw_stickers(late, scene, 0.45)
        self.assertNotEqual(early.tobytes(), late.tobytes())

    def test_float_animation_changes_frame(self):
        scene = {"stickers": [{"id": "brain", "x": 0.5, "y": 0.4,
                               "size": 140, "start": 0.0, "end": 1.0,
                               "animation": "float"}]}
        first = Image.new("RGB", (640, 360), "black")
        second = first.copy()
        draw_stickers(first, scene, 0.15)
        draw_stickers(second, scene, 0.65)
        self.assertNotEqual(first.tobytes(), second.tobytes())

    def test_unknown_sticker_is_ignored(self):
        image = Image.new("RGB", (320, 180), "black")
        before = image.copy()
        draw_stickers(image, {"stickers": [{"id": "not-real"}]}, 0.5)
        self.assertIsNone(ImageChops.difference(image, before).getbbox())


if __name__ == "__main__":
    unittest.main()
