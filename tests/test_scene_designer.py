import unittest

from scene_designer import design_story, split_beats


class SceneDesignerTests(unittest.TestCase):
    def test_splits_story_into_multiple_timed_shots(self):
        script = design_story(
            "The train left the platform. A locked service gate opened. "
            "He ran into the tunnel. A shadow waited at the exit.",
            24, "Night Train",
        )
        self.assertEqual(len(script["scenes"]), 4)
        self.assertEqual(script["scenes"][0]["environment"], "platform")
        self.assertEqual(script["scenes"][1]["environment"], "service_gate")
        self.assertEqual(script["scenes"][2]["environment"], "tunnel")
        self.assertEqual(script["scenes"][3]["environment"], "exit")
        self.assertEqual(script["scenes"][-1]["end"], 24)

    def test_shot_types_and_camera_compositions_vary(self):
        script = design_story(
            "He entered the hallway. He heard a whisper. He looked back. "
            "He ran toward the street. A shadow appeared.",
            30,
        )
        shots = [s["shot_design"]["shot_type"] for s in script["scenes"]]
        self.assertGreater(len(set(shots)), 1)
        self.assertGreater(len({s["camera"]["pan"] for s in script["scenes"]}), 1)

    def test_duration_and_empty_text_are_validated(self):
        with self.assertRaises(ValueError):
            design_story("   ", 10)
        with self.assertRaises(ValueError):
            design_story("A story.", 0)


if __name__ == "__main__":
    unittest.main()
