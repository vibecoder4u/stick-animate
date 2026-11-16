import json
import unittest
from pathlib import Path

from PIL import Image, ImageChops

from character_rigs import draw_species_character


class RiverbankPrototypeTests(unittest.TestCase):
    def test_new_script_has_all_four_characters_and_multiple_scenes(self):
        plan = json.loads(Path("demo/riverbank-rescue.json").read_text(encoding="utf-8"))
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


if __name__ == "__main__":
    unittest.main()
