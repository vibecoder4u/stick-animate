import json
import unittest
from pathlib import Path
from PIL import Image, ImageChops
from character_rigs import available_species, draw_species_character
from stick_animate import validate_script

class EnsembleCastTests(unittest.TestCase):
    def test_ensemble_demo_contains_nine_distinct_characters(self):
        plan = json.loads(Path("demo/forest-friends-ensemble.json").read_text(encoding="utf-8"))
        validate_script(plan)
        ids = {a.get("character_id") for s in plan["scenes"] for a in s.get("actors", []) if a.get("character_id")}
        species = {a.get("species") for s in plan["scenes"] for a in s.get("actors", [])}
        self.assertEqual(len(ids), 9)
        self.assertTrue({"human","monkey","turtle","bear","fox","rabbit","deer","elephant","bird"}.issubset(species))
        self.assertEqual(len(plan["scenes"][-1]["actors"]), 9)

    def test_all_animal_rigs_are_drawable_and_species_have_distinct_silhouettes(self):
        rendered = {}
        for species in available_species():
            if species == "human":
                continue
            image = Image.new("RGB", (640, 360), (30, 35, 45))
            self.assertTrue(draw_species_character(image, {"species": species, "scale": 0.7},
                {"x": 320, "y": 300, "pose": "walk", "facing": 1}, 0.4), species)
            rendered[species] = image
        self.assertGreaterEqual(len(rendered), 12)
        for a, b in (("fox","elephant"),("rabbit","turtle"),("deer","bear"),("bird","monkey")):
            self.assertIsNotNone(ImageChops.difference(rendered[a], rendered[b]).getbbox())

    def test_keyframed_prop_angle_changes_during_teamwork(self):
        from stick_animate import sample_keyframes
        from character_rigs import draw_species_character
        keys = [
            {"t": 0, "x": 300, "y": 250, "angle": -3, "pose": "idle"},
            {"t": 1, "x": 360, "y": 250, "angle": -18, "pose": "idle"},
        ]
        early = sample_keyframes(keys, 0.1)
        late = sample_keyframes(keys, 0.9)
        self.assertNotEqual(early["angle"], late["angle"])
        frames = []
        for pose in (early, late):
            image = Image.new("RGB", (640, 360), (30, 35, 45))
            draw_species_character(image, {"species": "fallen_tree", "length": 420, **pose}, pose, 0.5)
            frames.append(image)
        self.assertIsNotNone(ImageChops.difference(*frames).getbbox())

    def test_ensemble_teamwork_scene_has_pushers_and_helpers(self):
        plan = json.loads(Path("demo/forest-friends-ensemble.json").read_text(encoding="utf-8"))
        scene = plan["scenes"][2]
        actions = {a.get("character_id"): a["keyframes"][-1]["pose"] for a in scene["actors"] if a.get("character_id")}
        self.assertEqual(actions["bruno"], "push")
        self.assertEqual(actions["umbo"], "push")
        self.assertEqual(actions["alex"], "push")
        self.assertEqual(actions["milo"], "reach")
        self.assertEqual(actions["tia"], "reach")

if __name__ == "__main__":
    unittest.main()
