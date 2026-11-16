import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asset_generator import ImageGenerator, ImageGenerationUnavailable, collect_asset_requests, prepare_generated_assets


class AssetDiscoveryTests(unittest.TestCase):
    def test_discovers_unknown_species_and_story_specific_props(self):
        script = {"scenes": [{"start": 0, "end": 3,
            "actors": [{"species": "phoenix", "name": "Ember"}],
            "props": [{"type": "crystal_compass"}]}]}
        requests = collect_asset_requests(script)
        self.assertEqual({item["kind"] for item in requests}, {"character", "prop"})
        self.assertTrue(any("phoenix" in item["prompt"].lower() for item in requests))
        self.assertTrue(any(item["asset_id"] == "prop-crystal-compass" for item in requests))

    def test_deduplicates_explicit_asset_requests(self):
        script = {"asset_requests": [
            {"asset_id": "moon-gate", "name": "Moon Gate", "kind": "prop"},
            {"asset_id": "moon-gate", "name": "Moon Gate", "kind": "prop"}],
            "scenes": []}
        self.assertEqual(len(collect_asset_requests(script)), 1)

    def test_background_prompt_becomes_generation_request(self):
        script = {"scenes": [{"start": 0, "end": 2, "environment": "crystal city",
                              "background_prompt": "A vast city made of blue crystal at sunrise"}]}
        request = collect_asset_requests(script)[0]
        self.assertEqual(request["kind"], "background")
        self.assertIn("blue crystal", request["prompt"])

    def test_no_provider_is_explicitly_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            generator = ImageGenerator()
            self.assertFalse(generator.available)
            with self.assertRaises(ImageGenerationUnavailable):
                generator.generate({"prompt": "test"}, Path("unused.png"))

    def test_missing_provider_warns_and_does_not_fake_assets(self):
        script = {"asset_requests": [{"asset_id": "new-creature", "name": "New creature"}], "scenes": []}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            self.assertEqual(prepare_generated_assets(script, Path(tmp)), {})
            self.assertFalse((Path(tmp) / "generated-assets.json").exists())

    def test_generated_asset_cache_is_reused(self):
        class FakeGenerator:
            provider = "fake"
            model = "test"
            available = True
            calls = 0
            def generate(self, request, destination):
                self.calls += 1
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"x" * 2048)
                return destination
        script = {"asset_requests": [{"asset_id": "new-prop", "name": "New prop"}], "scenes": []}
        fake = FakeGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            first = prepare_generated_assets(script, Path(tmp), fake)
            second = prepare_generated_assets(script, Path(tmp), fake)
            self.assertEqual(first, second)
            self.assertEqual(fake.calls, 1)
            manifest = json.loads((Path(tmp) / "generated-assets.json").read_text())
            self.assertIn("new-prop", manifest)


if __name__ == "__main__":
    unittest.main()
