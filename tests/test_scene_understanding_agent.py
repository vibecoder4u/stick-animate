import unittest

from scene_understanding_agent import analyse_script
from audio_director import plan_scene_audio


class SceneUnderstandingAgentTests(unittest.TestCase):
    def test_understands_narrative_without_treating_words_as_sound_events(self):
        script = {"title": "A mystery", "duration": 5, "scenes": [
            {"start": 0, "end": 5, "environment": "corridor",
             "caption": "He heard footsteps in the dark. Rain was falling outside.",
             "actor": {"keyframes": [{"t": 0, "x": 100, "pose": "idle"},
                                     {"t": 1, "x": 100, "pose": "idle"}]}}
        ]}
        report = analyse_script(script)
        self.assertIn("suspense", report["overall_themes"])
        self.assertIn("pursuit", report["overall_themes"])
        self.assertFalse(report["scenes"][0]["narration_is_sound_evidence"])
        self.assertEqual(plan_scene_audio(script), [])

    def test_visual_locomotion_authorizes_footsteps(self):
        script = {"duration": 4, "scenes": [
            {"start": 0, "end": 4, "environment": "corridor",
             "caption": "He stood still.",
             "actor": {"keyframes": [{"t": 0, "x": 100, "pose": "walk"},
                                     {"t": 1, "x": 260, "pose": "walk"}]}}
        ]}
        self.assertEqual([c["event"] for c in plan_scene_audio(script)], ["footsteps"])

    def test_rain_requires_explicit_scene_weather_or_rain_environment(self):
        dry = {"duration": 2, "scenes": [
            {"start": 0, "end": 2, "environment": "street",
             "caption": "Rain hammered the windows."}
        ]}
        wet = {"duration": 2, "scenes": [
            {"start": 0, "end": 2, "environment": "street", "weather": "rain"}
        ]}
        self.assertEqual(plan_scene_audio(dry), [])
        self.assertEqual([c["event"] for c in plan_scene_audio(wet)], ["rain"])


if __name__ == "__main__":
    unittest.main()
