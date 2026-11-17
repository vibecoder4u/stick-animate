from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops

from visual_library import (
    DEFAULT_ASSETS, materialize_visual_library, prepare_scene_overlays,
    render_visual_overlays, infer_scene_overlays,
)


class SmartVisualLibraryTests(unittest.TestCase):
    def test_all_starter_symbols_materialize_as_hash_addressed_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = materialize_visual_library(root)
            self.assertEqual(set(paths), set(DEFAULT_ASSETS))
            for asset_id, path in paths.items():
                target = Path(path)
                self.assertTrue(target.is_file(), asset_id)
                self.assertEqual(target.suffix, ".svg")
                self.assertEqual(len(target.stem), 64)
            manifest = json.loads((root / "visual-library-manifest.json").read_text())
            self.assertEqual(len(manifest["assets"]), len(DEFAULT_ASSETS))

    def test_repeated_materialization_reuses_same_hash_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = materialize_visual_library(Path(tmp))
            count = len(list((Path(tmp) / "visual-library").glob("*.svg")))
            second = materialize_visual_library(Path(tmp))
            self.assertEqual(first, second)
            self.assertEqual(count, len(list((Path(tmp) / "visual-library").glob("*.svg"))))

    def test_inference_maps_psychology_narration_to_meaningful_visual(self):
        scene = {"narration": "Humans are intelligent. The brain helps us reason and remember."}
        overlays = infer_scene_overlays(scene)
        self.assertEqual(overlays[0]["asset"], "bird_cross" if "cannot fly" in scene["narration"] else "brain")
        explicit = {"narration": "Humans cannot fly, despite their intelligence."}
        self.assertEqual(infer_scene_overlays(explicit)[0]["asset"], "bird_cross")

    def test_explicit_overlay_has_animated_enter_and_exit_and_renders(self):
        scene = {"visual_overlays": [{
            "asset": "brain", "visual_type": "thought_bubble", "text": "THE MIND",
            "start": 0.2, "end": 0.85, "enter": "slide_up", "exit": "slide_left",
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            paths = materialize_visual_library(Path(tmp))
            background = Image.new("RGB", (1280,720), (28,42,58))
            before = render_visual_overlays(background, scene, 0.1, paths)
            entrance = render_visual_overlays(background, scene, 0.25, paths)
            hold = render_visual_overlays(background, scene, 0.52, paths)
            exit_frame = render_visual_overlays(background, scene, 0.83, paths)
            self.assertIsNone(ImageChops.difference(background, before).getbbox())
            self.assertIsNotNone(ImageChops.difference(background, entrance).getbbox())
            self.assertIsNotNone(ImageChops.difference(background, hold).getbbox())
            self.assertIsNotNone(ImageChops.difference(background, exit_frame).getbbox())

    def test_unknown_concept_blueprint_is_drawn_as_new_hashed_svg_and_rendered(self):
        from concept_drawer import create_concept_asset, validate_blueprint
        blueprint = {
            "name": "tangled thoughts",
            "description": "A head surrounded by tangled thought lines",
            "elements": [
                {"type": "circle", "x": 64, "y": 68, "r": 34, "fill": "#F2C6A8", "stroke": "#40566A", "stroke_width": 4},
                {"type": "polyline", "points": [[42,65],[52,54],[60,67],[70,49],[82,64],[91,55]], "fill": "none", "stroke": "#7656A8", "stroke_width": 5},
                {"type": "circle", "x": 52, "y": 78, "r": 3, "fill": "#24394A", "stroke": "none"},
                {"type": "circle", "x": 76, "y": 78, "r": 3, "fill": "#24394A", "stroke": "none"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            made = create_concept_asset(blueprint, Path(tmp))
            self.assertTrue(Path(made["svg_path"]).is_file())
            self.assertTrue(Path(made["preview_path"]).is_file())
            self.assertEqual(len(made["sha256"]), 64)
            script = {"scenes": [{"narration": "A completely new concept",
                "visual_overlays": [{"asset": "tangled_thoughts", "visual_design": blueprint,
                    "visual_type": "thought_bubble", "start": .1, "end": .9}]}]}
            self.assertEqual(prepare_scene_overlays(script, Path(tmp)), 1)
            overlay = script["scenes"][0]["visual_overlays"][0]
            self.assertTrue(Path(overlay["_generated_preview_path"]).is_file())
            bg = Image.new("RGB", (1280, 720), (28, 42, 58))
            frame = render_visual_overlays(bg, script["scenes"][0], .5, {})
            self.assertIsNotNone(ImageChops.difference(bg, frame).getbbox())

    def test_rejects_unsafe_or_unsupported_blueprint_elements(self):
        from concept_drawer import validate_blueprint
        with self.assertRaises(ValueError):
            validate_blueprint({"elements": [{"type": "script", "text": "bad"}]})
        with self.assertRaises(ValueError):
            validate_blueprint({"elements": [{"type": "polygon", "points": [[1, 2]]}]})

    def test_scene_preparation_preserves_explicit_and_infers_missing(self):
        script = {"scenes": [
            {"narration": "The brain searches for memories."},
            {"narration": "A bird cannot fly?"},
            {"narration": "A different scene", "visual_overlays": [
                {"asset": "airplane", "visual_type": "sticker", "start": .2, "end": .8}
            ]}
        ]}
        count = prepare_scene_overlays(script)
        self.assertEqual(count, 3)
        self.assertEqual(script["scenes"][0]["visual_overlays"][0]["asset"], "brain")
        self.assertEqual(script["scenes"][1]["visual_overlays"][0]["asset"], "bird_cross")
        self.assertEqual(script["scenes"][2]["visual_overlays"][0]["asset"], "airplane")


if __name__ == "__main__":
    unittest.main()
