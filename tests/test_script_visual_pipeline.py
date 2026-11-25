import unittest

from scene_designer import design_story
from visual_story_director import apply_visual_direction


class ScriptVisualPipelineTests(unittest.TestCase):
    def test_plain_script_gets_human_story_anchors_and_semantic_stickers(self):
        story = "Your brain stores memories. You practise and learn new skills."
        plan = design_story(story, title="Learning")
        apply_visual_direction(plan, story)

        self.assertEqual(len(plan["scenes"]), 2)
        self.assertTrue(all(scene.get("actor") for scene in plan["scenes"]))
        self.assertTrue(all(scene["actor"]["species"] == "human" for scene in plan["scenes"]))
        sticker_ids = [scene["stickers"][0]["id"] for scene in plan["scenes"]]
        self.assertEqual(sticker_ids, ["brain", "book"])
        self.assertTrue(all(scene["stickers"][0]["animation"] in {"pop", "float"} for scene in plan["scenes"]))

    def test_authored_stickers_are_not_overwritten(self):
        plan = {"scenes": [{
            "start": 0, "end": 3, "description": "A student learns about memory.",
            "stickers": [{"id": "heart", "x": 0.3, "y": 0.3, "size": 160, "animation": "pulse"}]
        }]}
        apply_visual_direction(plan, "A student learns about memory.")
        self.assertEqual(plan["scenes"][0]["stickers"][0]["id"], "heart")
        self.assertEqual(plan["scenes"][0]["stickers"][0]["animation"], "pulse")


if __name__ == "__main__":
    unittest.main()
