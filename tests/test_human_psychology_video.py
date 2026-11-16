import json
import unittest
from pathlib import Path

from stick_animate import validate_script


class HumanPsychologyVideoTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parents[1] / "demo" / "human-psychology-overthinking.json"
        self.script = json.loads(self.path.read_text(encoding="utf-8"))

    def test_documentary_timeline_is_valid(self):
        validate_script(self.script)
        self.assertEqual(self.script["duration"], 30)
        self.assertEqual(len(self.script["scenes"]), 5)

    def test_every_scene_has_narration_and_caption(self):
        for scene in self.script["scenes"]:
            self.assertTrue(scene.get("narration", "").strip())
            self.assertTrue(scene.get("caption", "").strip())

    def test_human_cast_and_flashback_are_present(self):
        cast = {
            actor["character_id"]
            for scene in self.script["scenes"]
            for actor in scene.get("actors", [])
        }
        self.assertIn("maya", cast)
        self.assertIn("friend", cast)
        self.assertIn("maya_memory", cast)


if __name__ == "__main__":
    unittest.main()
