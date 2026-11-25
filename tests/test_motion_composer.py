import math
import unittest

from motion_composer import compose_motion, motion_for_actor


class MotionComposerTests(unittest.TestCase):
    def test_motion_is_bounded_and_deterministic(self):
        for pose in ("idle", "walk", "run", "jump", "push", "reach", "think"):
            a = compose_motion(pose, 0.4, 7)
            b = compose_motion(pose, 0.4, 7)
            self.assertEqual(a, b)
            self.assertTrue(all(math.isfinite(value) for value in a.values()))
            self.assertLessEqual(abs(a["torso_lean"]), 20)

    def test_walk_and_run_have_distinct_cycle_rates(self):
        walk = compose_motion("walk", 0.5, 0)["phase"]
        run = compose_motion("run", 0.5, 0)["phase"]
        self.assertNotEqual(walk, run)
        self.assertGreater(run, walk)

    def test_action_has_anticipation_and_follow_through(self):
        early = compose_motion("jump", 0.05, 0)
        late = compose_motion("jump", 0.95, 0)
        self.assertGreater(early["anticipation"], 0)
        self.assertGreater(late["follow_through"], 0.9)

    def test_actor_seed_keeps_motion_identity_stable(self):
        actor = {"character_id": "woman_1", "keyframes": [{"pose": "walk"}]}
        self.assertEqual(motion_for_actor(actor, 0.3), motion_for_actor(actor, 0.3))


if __name__ == "__main__":
    unittest.main()
