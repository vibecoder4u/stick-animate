import json
import unittest
from pathlib import Path

from PIL import Image

import stick_animate


ROOT = Path(__file__).resolve().parents[1]


class AnimationEngineTests(unittest.TestCase):
    def setUp(self):
        self.script = json.loads((ROOT / "demo" / "mystery_hallway.json").read_text(encoding="utf-8"))

    def test_demo_script_is_valid_and_covers_30_seconds(self):
        stick_animate.validate_script(self.script)
        self.assertEqual(self.script["duration"], 30)
        self.assertEqual(len(self.script["scenes"]), 5)
        self.assertEqual(self.script["scenes"][0]["start"], 0)
        self.assertEqual(self.script["scenes"][-1]["end"], 30)

    def test_keyframe_interpolation_is_smooth_and_reaches_endpoints(self):
        keys = [
            {"t": 0, "x": 100, "y": 500, "pose": "walk"},
            {"t": 1, "x": 500, "y": 500, "pose": "idle"},
        ]
        self.assertEqual(stick_animate.sample_keyframes(keys, 0)["x"], 100)
        self.assertEqual(stick_animate.sample_keyframes(keys, 1)["x"], 500)
        middle = stick_animate.sample_keyframes(keys, 0.5)
        self.assertAlmostEqual(middle["x"], 300)
        self.assertEqual(middle["pose"], "idle")

    def test_frame_renderer_returns_full_hd_rgb_frame(self):
        scene = self.script["scenes"][2]
        frame = stick_animate.make_frame(self.script, scene, 0.5, 15.0, {})
        self.assertIsInstance(frame, Image.Image)
        self.assertEqual(frame.mode, "RGB")
        self.assertEqual(frame.size, (1280, 720))

    def test_invalid_overlapping_scenes_are_rejected(self):
        invalid = dict(self.script)
        invalid["scenes"] = [dict(self.script["scenes"][0]), dict(self.script["scenes"][1])]
        invalid["scenes"][1]["start"] = 4
        with self.assertRaises(ValueError):
            stick_animate.validate_script(invalid)


if __name__ == "__main__":
    unittest.main()
