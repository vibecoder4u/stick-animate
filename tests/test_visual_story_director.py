import unittest

from visual_story_director import apply_visual_direction, classify_beat, split_script_beats


class VisualStoryDirectorTests(unittest.TestCase):
    def test_script_is_split_into_ordered_beats(self):
        beats = split_script_beats("Maya felt afraid. She ran outside.\n\nThen she found her friend.")
        self.assertEqual(len(beats), 3)
        self.assertIn("Maya", beats[0])
        self.assertIn("friend", beats[2])

    def test_different_script_beats_get_different_story_roles(self):
        opening = classify_beat("A lonely boy entered the empty room.", 0, 4)
        action = classify_beat("He ran toward the door.", 1, 4)
        discovery = classify_beat("Suddenly, he discovered a letter.", 2, 4)
        ending = classify_beat("He understood that his friend had returned.", 3, 4)
        self.assertEqual(opening["role"], "opening")
        self.assertEqual(action["action"], "run")
        self.assertEqual(discovery["role"], "discovery")
        self.assertEqual(ending["role"], "discovery")

    def test_direction_adds_script_specific_intent_and_camera_defaults(self):
        plan = {
            "scenes": [
                {"start": 0, "end": 3, "description": "A woman enters a quiet classroom.",
                 "actors": [{"character_id": "woman_1", "expression": "neutral", "keyframes": []}]},
                {"start": 3, "end": 6, "description": "She suddenly discovers the answer in a book.",
                 "camera": {"zoom_start": 1.0, "zoom_end": 1.02}},
                {"start": 6, "end": 9, "description": "She smiles and celebrates with her friend."},
            ]
        }
        script = ("A woman enters a quiet classroom. "
                  "She suddenly discovers the answer in a book. "
                  "She smiles and celebrates with her friend.")
        result = apply_visual_direction(plan, script)
        self.assertEqual(result["design_metadata"]["visual_direction"]["scene_count"], 3)
        self.assertEqual(result["scenes"][0]["visual_direction"]["purpose"], "opening")
        self.assertEqual(result["scenes"][1]["visual_direction"]["purpose"], "discovery")
        self.assertEqual(result["scenes"][1]["camera"]["zoom_end"], 1.02)
        self.assertIn("shot_type", result["scenes"][1]["camera"])
        self.assertEqual(result["scenes"][0]["actors"][0]["expression"], "neutral")
        self.assertIn("script_evidence", result["scenes"][2]["visual_direction"])

    def test_authored_camera_choices_are_preserved(self):
        plan = {"scenes": [{"start": 0, "end": 2, "description": "A man runs.",
                            "camera": {"shot_type": "custom_tracking", "zoom_start": 1.2}}]}
        apply_visual_direction(plan, "A man runs.")
        self.assertEqual(plan["scenes"][0]["camera"]["shot_type"], "custom_tracking")
        self.assertEqual(plan["scenes"][0]["camera"]["zoom_start"], 1.2)


if __name__ == "__main__":
    unittest.main()
