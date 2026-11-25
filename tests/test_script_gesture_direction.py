import unittest

from visual_story_director import apply_visual_direction, classify_beat


class ScriptGestureDirectionTests(unittest.TestCase):
    def test_new_human_gestures_are_inferred(self):
        cases = {
            "Maya waved goodbye to her brother.": "wave",
            "The teacher pointed at the answer.": "point",
            "He celebrated the victory.": "celebrate",
            "She comforted her frightened friend.": "comfort",
            "The child sat beside the window.": "sit",
            "The old man knelt beside the bag.": "kneel",
            "Maya opened the locked door.": "open",
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence):
                self.assertEqual(classify_beat(sentence, 1, 3)["action"], expected)

    def test_director_assigns_inferred_gesture_to_idle_actor(self):
        plan = {"scenes": [{
            "start": 0, "end": 2, "description": "Maya waved goodbye.",
            "actors": [{"character_id": "woman_1", "species": "human",
                        "keyframes": [{"t": 0, "x": 300, "y": 610, "pose": "idle"},
                                      {"t": 1, "x": 300, "y": 610, "pose": "idle"}]}]
        }]}
        apply_visual_direction(plan, "Maya waved goodbye.")
        poses = [key["pose"] for key in plan["scenes"][0]["actors"][0]["keyframes"]]
        self.assertEqual(poses, ["wave", "wave"])


if __name__ == "__main__":
    unittest.main()
