import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_generator import collect_asset_requests, prepare_generated_assets, attach_generated_assets
from native_artwork import create_native_asset, draw_native_character


class NativeAssetPipelineTests(unittest.TestCase):
    def test_discovers_unknown_species_and_props_without_external_provider(self):
        script = {"scenes": [{"start": 0, "end": 3,
            "actors": [{"species": "penguin", "name": "Pip",
                        "visual_description": "A tiny emperor penguin with a teal scarf"}],
            "props": [{"type": "hover_bike"}]}]}
        requests = collect_asset_requests(script)
        self.assertEqual({item["kind"] for item in requests}, {"character", "prop"})
        self.assertTrue(any("penguin" in item["prompt"].lower() for item in requests))
        self.assertTrue(any(item["asset_id"] == "prop-hover-bike" for item in requests))
        self.assertEqual(next(x for x in requests if x["kind"] == "character")["visual_design"], {})

    def test_deduplicates_explicit_asset_requests(self):
        script = {"asset_requests": [
            {"asset_id": "moon-gate", "name": "Moon Gate", "kind": "prop"},
            {"asset_id": "moon-gate", "name": "Moon Gate", "kind": "prop"}],
            "scenes": []}
        self.assertEqual(len(collect_asset_requests(script)), 1)

    def test_background_prompt_becomes_native_background_request(self):
        script = {"scenes": [{"start": 0, "end": 2, "environment": "crystal city",
                              "background_prompt": "A vast city made of blue crystal at sunrise"}]}
        request = collect_asset_requests(script)[0]
        self.assertEqual(request["kind"], "background")
        self.assertIn("blue crystal", request["prompt"])

    def test_compiles_svg_preview_layers_and_metadata(self):
        request = {"asset_id": "character-penguin", "name": "Pip", "kind": "character",
                   "prompt": "An emperor penguin with a teal scarf",
                   "visual_design": {"anatomy": "bird", "palette": "cool",
                       "distinctive_features": ["teal scarf", "gold chest patch"]}}
        with tempfile.TemporaryDirectory() as tmp:
            result = create_native_asset(request, Path(tmp))
            self.assertTrue(Path(result["path"]).is_file())
            self.assertTrue(Path(result["svg_path"]).is_file())
            self.assertTrue(Path(result["metadata_path"]).is_file())
            metadata = json.loads(Path(result["metadata_path"]).read_text())
            self.assertEqual(metadata["renderer"], "native-artwork-v1")
            self.assertTrue(list(Path(result["layers_path"]).glob("*.png")))
            preview = Image.open(result["path"])
            self.assertEqual(preview.mode, "RGBA")

    def test_native_asset_cache_is_reused(self):
        script = {"asset_requests": [{"asset_id": "new-prop", "name": "Crystal compass",
                                      "kind": "prop"}], "scenes": []}
        with tempfile.TemporaryDirectory() as tmp:
            first = prepare_generated_assets(script, Path(tmp))
            second = prepare_generated_assets(script, Path(tmp))
            self.assertEqual(first, second)
            manifest = json.loads((Path(tmp) / "native-assets" / "manifest.json").read_text())
            self.assertIn("new-prop", manifest)

    def test_paths_attach_to_actor_prop_and_background(self):
        script = {"scenes": [{"start": 0, "end": 2, "background_asset": "scene-bg",
            "actors": [{"name": "Pip", "asset_id": "character-pip"}],
            "props": [{"type": "hover_bike", "asset_id": "prop-hover-bike"}]}]}
        generated = {"scene-bg": "/tmp/bg.png", "character-pip": "/tmp/pip.png",
                     "prop-hover-bike": "/tmp/bike.png"}
        attach_generated_assets(script, generated)
        scene = script["scenes"][0]
        self.assertEqual(scene["background_image"], "/tmp/bg.png")
        self.assertEqual(scene["actors"][0]["_native_asset_path"], "/tmp/pip.png")
        self.assertEqual(scene["props"][0]["_native_asset_path"], "/tmp/bike.png")

    def test_unknown_character_is_drawn_with_native_anatomy_rig(self):
        image = Image.new("RGBA", (640, 360), (0, 0, 0, 0))
        drawn = draw_native_character(image, {"species": "penguin", "name": "Pip",
            "visual_description": "A small penguin"}, {"x": 320, "y": 300, "pose": "walk",
            "gait_phase": 1.2}, 0.4)
        self.assertTrue(drawn)
        self.assertIsNotNone(image.getbbox())

    def test_unknown_prop_and_background_are_compiled(self):
        with tempfile.TemporaryDirectory() as tmp:
            for kind, name in (("prop", "hover bike"), ("background", "crystal mountain valley")):
                result = create_native_asset({"name": name, "kind": kind, "prompt": name}, Path(tmp))
                self.assertTrue(Path(result["path"]).is_file())
                self.assertTrue(Path(result["svg_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
