import json
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from unittest.mock import patch

from sound_effect_finder import find_and_mix_effects, search_openverse


class SoundEffectFinderTests(unittest.TestCase):
    def _write_wav(self, path, channels, samples):
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(array("h", samples).tobytes())

    def test_unknown_event_does_not_call_external_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sound_effect_finder._request_json") as request:
                self.assertIsNone(search_openverse("made_up_event", Path(tmp)))
                request.assert_not_called()

    def test_openverse_query_restricts_to_commercial_licenses(self):
        item = {
            "url": "https://example.test/audio.mp3",
            "title": "Forest footsteps",
            "creator": "Sound Artist",
            "license": "by",
            "license_version": "4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "foreign_landing_url": "https://example.test/track",
            "attribution": "Forest footsteps by Sound Artist, CC BY 4.0",
            "tags": [{"name": "forest"}, {"name": "footsteps"}],
        }
        def fake_download(url, target):
            target.write_bytes(b"x" * 2048)
            return True
        def fake_ffmpeg(args, **kwargs):
            self._write_wav(Path(args[-1]), 1, [1000] * 4096)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sound_effect_finder._request_json", return_value={"results": [
                {"url": "https://example.test/nc.mp3", "license": "by-nc", "title": "Forest"},
                item,
            ]}) as request, patch("sound_effect_finder._download", side_effect=fake_download), patch(
                "sound_effect_finder.subprocess.run", side_effect=fake_ffmpeg
            ):
                result = search_openverse("footsteps", Path(tmp))
            self.assertEqual(result["license"], "by")
            self.assertIn("license_type=commercial", request.call_args.args[0])

    def test_mixer_places_effect_at_authored_time_and_writes_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            cache.mkdir()
            base = root / "base.wav"
            self._write_wav(base, 2, [0] * (22050 * 2))
            self._write_wav(cache / "effect.wav", 1, [10000] * 22050)
            metadata = {
                "event": "wood_impact", "title": "Wood impact", "creator": "Artist",
                "source_url": "https://example.test/source", "license": "by",
                "local_file": "effect.wav",
            }
            cue = {"event": "wood_impact", "start": 0.2, "duration": 0.25, "gain": 0.5}
            with patch("sound_effect_finder.search_openverse", return_value=metadata):
                result = find_and_mix_effects(base, [cue], 1.0, cache, root / "attribution.json")
            self.assertEqual(len(result), 1)
            with wave.open(str(base), "rb") as wav:
                mixed = array("h")
                mixed.frombytes(wav.readframes(wav.getnframes()))
            self.assertEqual(mixed[0], 0)
            self.assertGreater(mixed[int(0.21 * 22050) * 2], 4000)
            self.assertEqual(mixed[int(0.8 * 22050) * 2], 0)
            manifest = json.loads((root / "attribution.json").read_text())
            self.assertEqual(manifest[0]["license"], "by")


if __name__ == "__main__":
    unittest.main()
