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

    def test_short_ai_outline_recovers_to_full_local_storyboard(self):
        story = ("Alex lived near a big forest, but he had no friends. Every day, he walked alone. "
                 "One day, he tripped and his apples rolled everywhere. \"Oh no, I have to do everything "
                 "alone again,\" he said. Then a small hand picked up an apple. \"You dropped this! "
                 "Are you okay?\" asked Milo the Monkey. Milo helped him, and Alex laughed. "
                 "They found Tia the Turtle stuck on her back. Friends don't leave friends behind, "
                 "so they pushed together until Tia was free. Then a storm came. A big tree blocked "
                 "the road. \"Need a paw?\" said Bruno the Bear. Together, they moved the tree. "
                 "That evening, Alex walked home with friends. A true friend stays when the storm comes.")
        class ShortOutline:
            available = True
            model = "test-model"
            def json_completion(self, system, user, temperature):
                return {"title": "Alex and the Forest of Friends", "size": [1280, 720], "fps": 24,
                        "scenes": [
                            {"start": 0, "end": 3, "description": "Alex alone"},
                            {"start": 3, "end": 6, "description": "Milo arrives"},
                            {"start": 6, "end": 9, "description": "Friends go home"},
                        ]}
        plan = design_production(story, title="Alex and the Forest of Friends", llm=ShortOutline())
        self.assertGreaterEqual(len(plan["scenes"]), 9)
        self.assertEqual(plan["design_metadata"]["creative_mode"], "hybrid_storyboard_recovery")
        self.assertIn("monkey", " ".join(str(s.get("actor", {})) for s in plan["scenes"]))
        self.assertIn("turtle", " ".join(str(s.get("actor", {})) for s in plan["scenes"]))
        self.assertIn("bear", " ".join(str(s.get("actor", {})) for s in plan["scenes"]))
        self.assertTrue(any(s.get("props") for s in plan["scenes"]))

    def test_ai_plan_must_cover_each_script_paragraph(self):
        story = "Alex meets Milo.\n\nThey rescue Tia.\n\nBruno helps move the tree."
        short_plan = {"scenes": [{"start": 0, "end": 2}, {"start": 2, "end": 4}]}
        with self.assertRaisesRegex(ValueError, "Story coverage incomplete"):
            _validate_plan(short_plan, story=story)
        complete_plan = {"scenes": [
            {"start": 0, "end": 2, "description": "Alex meets Milo"},
            {"start": 2, "end": 4, "description": "They rescue Tia"},
            {"start": 4, "end": 6, "description": "Bruno helps move the tree"},
        ]}
        self.assertEqual(_validate_plan(complete_plan, story=story), 6.0)

    def test_one_paragraph_story_requires_real_storyboard_coverage(self):
        story = ("Alex tripped and apples rolled away. Milo the Monkey helped him. "
                 "They found Tia the Turtle stuck on her back. A storm arrived and a tree blocked the road. "
                 "Bruno the Bear helped them push the tree aside. They walked home together as friends.")
        short = {"scenes": [{"start": 0, "end": 3}, {"start": 3, "end": 7}]}
        with self.assertRaisesRegex(ValueError, "require at least"):
            _validate_plan(short, story=story)

    def test_story_coverage_requires_distinctive_events(self):
        story = ("Alex tripped and apples rolled away. Milo the Monkey helped him. "
                 "They found Tia the Turtle stuck on her back. A storm arrived and a tree blocked the road. "
                 "Bruno the Bear helped them push the tree aside. They walked home together as friends.")
        scenes = []
        descriptions = [
            "Alex trips and apples roll across the forest floor",
            "Milo the Monkey picks up an apple and helps Alex",
            "Alex laughs with Milo the Monkey",
            "Tia the Turtle is stuck upside down",
            "Milo and Alex push Tia the Turtle upright",
            "A storm breaks over the forest road",
            "A fallen tree blocks the road",
            "Bruno the Bear arrives to help",
            "The friends push and move the fallen tree together",
            "Alex walks home with Milo Tia and Bruno as friends",
        ]
        for i, description in enumerate(descriptions):
            scene = {"start": i * 4, "end": (i + 1) * 4, "description": description}\n            for species in ("monkey", "turtle", "bear"):\n                if species in description.lower():\n                    scene["actors"] = [{"species": species, "character_id": species}]\n                    break\n            scenes.append(scene)
        plan = {"scenes": scenes}
        self.assertEqual(_validate_plan(plan, story=story), 40.0)
        for scene in plan["scenes"]:
            scene["description"] = scene["description"].replace("apples", "fruit").replace("apple", "fruit")
            scene["caption"] = scene["caption"].lower().replace("apples", "fruit").replace("apple", "fruit")
        with self.assertRaisesRegex(ValueError, "apple"):
            _validate_plan(plan, story=story)

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
