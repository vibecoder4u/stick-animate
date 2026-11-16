import json
import unittest
from pathlib import Path

from PIL import Image, ImageChops

from character_rigs import draw_species_character
from stick_animate import sample_keyframes, validate_script


class RiverbankPrototypeTests(unittest.TestCase):
    def test_new_script_has_all_four_characters_and_multiple_scenes(self):
        plan = json.loads(Path("demo/riverbank-rescue.json").read_text(encoding="utf-8"))
        validate_script(plan)
        self.assertEqual(plan["title"], "The Riverbank Rescue — Animation Test")
        self.assertGreaterEqual(len(plan["scenes"]), 5)
        species = {
            actor.get("species")
            for scene in plan["scenes"]
            for actor in scene.get("actors", [])
        }
        self.assertTrue({"human", "monkey", "turtle", "bear"}.issubset(species))

    def test_animal_rigs_change_between_locomotion_and_action(self):
        for species in ("monkey", "turtle", "bear"):
            frames = []
            for pose_name, t in (("walk", 0.25), ("push", 0.85)):
                image = Image.new("RGB", (640, 360), (30, 35, 45))
                drawn = draw_species_character(
                    image, {"species": species, "scale": 1.0},
                    {"x": 320, "y": 300, "pose": pose_name, "facing": 1}, t
                )
                self.assertTrue(drawn)
                frames.append(image)
            self.assertIsNotNone(ImageChops.difference(*frames).getbbox())

    def test_fallen_tree_and_apples_are_renderable_props(self):
        for prop in ({"species": "fallen_tree", "length": 500},
                     {"species": "apple_cluster", "count": 5}):
            image = Image.new("RGB", (640, 360), (30, 35, 45))
            self.assertTrue(draw_species_character(
                image, prop, {"x": 320, "y": 300, "pose": "idle"}, 0.5
            ))
            self.assertIsNotNone(ImageChops.difference(
                image, Image.new("RGB", image.size, (30, 35, 45))
            ).getbbox())


    def test_timeline_gap_is_rejected_instead_of_reusing_last_scene(self):
        bad = {
            "title": "gap", "duration": 2, "fps": 24,
            "scenes": [
                {"start": 0, "end": 0.8},
                {"start": 1.0, "end": 2.0},
            ],
        }
        with self.assertRaisesRegex(ValueError, "Timeline gap"):
            validate_script(bad)

    def test_all_cast_keyframes_are_validated_and_numeric_controls_interpolate(self):
        bad = {
            "title": "bad cast", "duration": 1, "fps": 24,
            "scenes": [{"start": 0, "end": 1, "actors": [
                {"species": "bear", "keyframes": [
                    {"t": 0, "x": 0}, {"t": 0.8, "x": 10}, {"t": 0.4, "x": 20}
                ]}
            ]}],
        }
        with self.assertRaisesRegex(ValueError, "Invalid keyframes"):
            validate_script(bad)
        sampled = sample_keyframes([
            {"t": 0, "x": 0, "action_progress": 0.0, "pose": "walk"},
            {"t": 1, "x": 100, "action_progress": 1.0, "pose": "push"},
        ], 0.25)
        self.assertGreater(sampled["x"], 0)
        self.assertGreater(sampled["action_progress"], 0)


if __name__ == "__main__":
    unittest.main()
