import json
import unittest
from pathlib import Path
from PIL import Image, ImageChops

from human_cast import HUMAN_CAST, character_profile, apply_age_variant
from sticker_library import STICKERS, draw_stickers
from stick_animate import validate_script, draw_character, draw_character_design

class HumanCastAndStickerTests(unittest.TestCase):
    def test_exactly_eight_approved_human_identities(self):
        self.assertEqual(len(HUMAN_CAST), 8)
        self.assertEqual(sum(x["gender"] == "male" for x in HUMAN_CAST.values()), 5)  # 3 men + 2 boys
        self.assertEqual(sum(x["gender"] == "female" for x in HUMAN_CAST.values()), 3)  # 2 women + 1 girl
        self.assertEqual([HUMAN_CAST[k]["age"] for k in ("child_5","child_9","child_13")], [5,9,13])

    def test_children_have_distinct_proportions(self):
        children=[character_profile(k) for k in ("child_5","child_9","child_13")]
        self.assertEqual(sorted(x["scale"] for x in children), [0.76,0.86,0.94])
        self.assertEqual(sorted(x["head_scale"] for x in children), [1.07,1.14,1.22])

    def test_character_profiles_render_with_distinct_colour_and_scale(self):
        renders=[]
        for cid in ("man_1","woman_1","child_5","child_9","child_13"):
            profile=character_profile(cid)
            image=Image.new("RGB",(640,360),(25,32,43))
            draw_character(image,320,315,"idle",1,0.2,profile["scale"],profile)
            renders.append(image)
        self.assertTrue(all(ImageChops.difference(renders[0],img).getbbox() for img in renders[1:]))

    def test_elderly_variant_adds_white_hair_and_cane(self):
        old=apply_age_variant(character_profile("man_2"),"elderly")
        self.assertEqual(old["hair"],"white")
        self.assertIn("walking_stick",old["accessories"])
        image=Image.new("RGB",(640,360),(25,32,43))
        draw_character_design(image,old,{"x":320,"y":315,"facing":1})

    def test_sticker_catalogue_has_svg_sources_and_runtime_rendering(self):
        self.assertGreaterEqual(len(STICKERS),10)
        self.assertTrue(all(item["svg"].startswith("<svg") for item in STICKERS.values()))
        base=Image.new("RGBA",(640,360),(20,30,40,255))
        scene={"stickers":[{"id":"brain","x":0.5,"y":0.4,"size":100},{"id":"question","x":0.75,"y":0.4,"size":80}]}
        draw_stickers(base,scene,0.5)
        self.assertIsNotNone(ImageChops.difference(base.convert("RGB"),Image.new("RGB",(640,360),(20,30,40))).getbbox())

    def test_one_minute_demo_has_eight_humans_and_sticker_overlays(self):
        data=json.loads(Path("demo/brain-learning-stickers-60s.json").read_text())
        validate_script(data)
        self.assertEqual(data["duration"],60)
        self.assertEqual(len(data["scenes"]),10)
        for scene in data["scenes"]:
            self.assertTrue(scene.get("stickers"))
            self.assertTrue(scene.get("narration"))
            for actor in scene.get("actors",[]):
                self.assertEqual(actor["species"],"human")
                self.assertIn(actor["character_id"],HUMAN_CAST)

if __name__ == "__main__":
    unittest.main()
