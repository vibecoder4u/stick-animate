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

    def test_structured_canvas_size_is_normalized(self):
        plan = {"size": {"width": 1280, "height": 720},
                "scenes": [{"start": 0, "end": 2}]}
        _validate_plan(plan)
        self.assertEqual(plan["size"], [1280, 720])

    def test_invalid_canvas_size_is_rejected(self):
        plan = {"size": {"width": "width", "height": "height"},
                "scenes": [{"start": 0, "end": 2}]}
        with self.assertRaisesRegex(ValueError, "numeric"):
            _validate_plan(plan)

    def test_ai_plan_must_cover_each_script_paragraph(self):
        story = "Alex meets Milo.\\n\\nThey rescue Tia.\\n\\nBruno helps move the tree."
        short_plan = {"scenes": [{"start": 0, "end": 2}, {"start": 2, "end": 4}]}
        with self.assertRaisesRegex(ValueError, "Story coverage incomplete"):
            _validate_plan(short_plan, story=story)
        complete_plan = {"scenes": [{"start": 0, "end": 2}, {"start": 2, "end": 4},
                                    {"start": 4, "end": 6}]}
        self.assertEqual(_validate_plan(complete_plan, story=story), 6.0)

    def test_auto_mode_preserves_natural_ai_timeline_without_stretching(self):
        plan = {"scenes": [{"start": 0, "end": 3.2}, {"start": 3.2, "end": 11.8}, {"start": 11.8, "end": 16.4}]}
        self.assertEqual(_validate_plan(plan, 30, 24, "auto"), 16.4)
        self.assertEqual(plan["scenes"][1]["start"], 3.2)
        self.assertEqual(plan["scenes"][-1]["end"], 16.4)

    def test_auto_mode_rejects_real_gaps_and_overlaps(self):
        with self.assertRaisesRegex(ValueError, "gap"):
            _validate_plan({"scenes": [{"start": 0, "end": 4}, {"start": 5, "end": 8}]}, None, 24, "auto")
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            _validate_plan({"scenes": [{"start": 0, "end": 5}, {"start": 4, "end": 8}]}, None, 24, "auto")

    def test_strict_mode_enforces_requested_runtime(self):
        plan = {"scenes": [{"start": 0, "end": 29.9}]}
        self.assertEqual(_validate_plan(plan, 30, 24, "strict"), 30.0)
        with self.assertRaisesRegex(ValueError, "Strict duration"):
            _validate_plan({"scenes": [{"start": 0, "end": 12}]}, 30, 24, "strict")

    def test_fallback_auto_timing_is_not_forced_to_target(self):
        story = "A boy waits alone. " + "He speaks with a friend and laughs. " * 4
        plan = design_production(story, 30, "Pacing test")
        self.assertNotEqual(plan["duration"], 30)
        self.assertEqual(plan["design_metadata"]["duration_policy"], "auto")

    def test_fallback_does_not_reuse_railway_story(self):
        plan = design_production("A fisherman rows across a lake. A storm breaks over the water. "
                                 "A strange light rises beneath his boat.", 24, "The Lake")
        descriptions = " ".join(s["description"].lower() for s in plan["scenes"])
        self.assertIn("fisherman", descriptions)
        self.assertNotIn("railway station", descriptions)

    def test_free_llm_is_optional(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            self.assertFalse(FreeLLM().available)

if __name__ == "__main__":
    unittest.main()
