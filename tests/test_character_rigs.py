import unittest
from PIL import Image, ImageChops

from character_rigs import available_species, draw_species_character


class SpeciesRigTests(unittest.TestCase):
    def test_species_have_distinct_anatomy_renderers(self):
        self.assertEqual(set(available_species()), {"human", "monkey", "turtle", "bear", "dog", "cat", "bird", "fish", "dinosaur"})
        outputs = {}
        for species in ("monkey", "turtle", "bear", "dog", "cat", "bird", "fish", "dinosaur"):
            image = Image.new("RGB", (640, 360), (30, 35, 45))
            drawn = draw_species_character(
                image, {"species": species, "scale": 1.0},
                {"x": 320, "y": 300, "pose": "run", "facing": 1}, 0.7
            )
            self.assertTrue(drawn)
            outputs[species] = image
        for a, b in (("monkey","turtle"),("bear","dog"),("dog","bird"),("cat","fish"),("dinosaur","dog")):
            self.assertIsNotNone(ImageChops.difference(outputs[a], outputs[b]).getbbox())

    def test_human_is_not_misrouted_to_animal_rig(self):
        image = Image.new("RGB", (640, 360), (30, 35, 45))
        self.assertFalse(draw_species_character(image, {"species":"human"}, {"x":320,"y":300}, 0))


if __name__ == "__main__":
    unittest.main()
