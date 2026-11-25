import unittest

from storyboard_qa import audit_storyboard


class StoryboardQATests(unittest.TestCase):
    def test_flags_repeated_composition_and_static_actors(self):
        plan = {"scenes": [
            {"camera": {"shot_type": "medium"}, "shot_design": {"primary_action": "idle"},
             "actor": {"character_id": "man_1", "keyframes": [{"t": 0, "x": 400, "y": 610, "pose": "idle"}, {"t": 1, "x": 400, "y": 610, "pose": "idle"}]}},
            {"camera": {"shot_type": "medium"}, "shot_design": {"primary_action": "idle"},
             "actor": {"character_id": "man_1", "keyframes": [{"t": 0, "x": 400, "y": 610, "pose": "idle"}, {"t": 1, "x": 400, "y": 610, "pose": "idle"}]}},
        ]}
        result = audit_storyboard(plan)
        codes = {item["code"] for item in result["warnings"]}
        self.assertIn("static_actor", codes)
        self.assertIn("repeated_composition", codes)

    def test_diversity_scores_are_bounded(self):
        result = audit_storyboard({"scenes": [
            {"camera": {"shot_type": "wide"}, "shot_design": {"primary_action": "walk"}},
            {"camera": {"shot_type": "close"}, "shot_design": {"primary_action": "point"}},
        ]})
        self.assertGreaterEqual(result["action_diversity"], 0)
        self.assertLessEqual(result["action_diversity"], 1)
        self.assertEqual(result["warning_count"], len(result["warnings"]))


if __name__ == "__main__":
    unittest.main()
