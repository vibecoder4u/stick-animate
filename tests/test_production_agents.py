import unittest
from unittest.mock import patch

from production_agents import design_production
from agent_runtime import FreeLLM


class ProductionAgentTests(unittest.TestCase):
    def test_free_mode_generates_script_specific_multiple_scenes(self):
        story = ("A girl discovers a fossil in a desert cave. "
                 "She climbs a narrow staircase into a museum. "
                 "A giant dinosaur skeleton moves behind her.")
        plan = design_production(story, 30, "The Fossil")
        self.assertGreaterEqual(len(plan["scenes"]), 3)
        self.assertEqual(plan["design_metadata"]["creative_mode"], "deterministic")
        # With no API key this is deliberately the local planner, not a fake
        # multi-agent/LLM run. Keep metadata honest and test the actual contract.
        self.assertEqual(plan["design_metadata"]["pipeline"], "local-fallback-no-api")
        self.assertTrue(all(scene.get("description") for scene in plan["scenes"]))

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
