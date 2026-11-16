import unittest
from unittest.mock import patch

from production_agents import _validate_plan, design_production
from agent_runtime import FreeLLM


class ProductionAgentTests(unittest.TestCase):
    def test_free_mode_generates_script_specific_multiple_scenes(self):
        story = ("A girl discovers a fossil in a desert cave. "
                 "She climbs a narrow staircase into a museum. "
                 "A giant dinosaur skeleton moves behind her.")
        plan = design_production(story, 30, "The Fossil")
        self.assertGreaterEqual(len(plan["scenes"]), 3)
        self.assertEqual(plan["design_metadata"]["creative_mode"], "deterministic")
        self.assertEqual(plan["design_metadata"]["pipeline"], "local-fallback-no-api")
        self.assertTrue(all(scene.get("description") for scene in plan["scenes"]))

    def test_ai_timeline_endpoint_drift_is_normalized(self):
        plan = {"scenes": [
            {"start": 0, "end": 9.93, "description": "Beat one"},
            {"start": 9.93, "end": 19.87, "description": "Beat two"},
            {"start": 19.87, "end": 29.8, "description": "Beat three"},
        ]}
        _validate_plan(plan, 30, 24)
        self.assertEqual(plan["scenes"][0]["start"], 0.0)
        self.assertEqual(plan["scenes"][-1]["end"], 30.0)
        self.assertAlmostEqual(plan["scenes"][1]["start"], 10.0, places=1)

    def test_ai_timeline_rejects_large_duration_mismatch(self):
        plan = {"scenes": [
            {"start": 0, "end": 4, "description": "Beat one"},
            {"start": 4, "end": 8, "description": "Beat two"},
        ]}
        with self.assertRaisesRegex(ValueError, "differs too much"):
            _validate_plan(plan, 30, 24)

    def test_fallback_does_not_reuse_railway_story(self):
        plan = design_production(
            "A fisherman rows across a lake. A storm breaks over the water. "
            "A strange light rises beneath his boat.", 24, "The Lake"
        )
        descriptions = " ".join(s["description"].lower() for s in plan["scenes"])
        self.assertIn("fisherman", descriptions)
        self.assertNotIn("railway station", descriptions)

    def test_free_llm_is_optional(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            self.assertFalse(FreeLLM().available)


if __name__ == "__main__":
    unittest.main()
