import unittest
from motion_engine import evaluate_motion, validate_path_points


class MotionEngineTests(unittest.TestCase):
    def test_diagonal_path_interpolates_both_axes(self):
        actor = {"path_points": [
            {"t": 0, "x": 100, "y": 600, "depth": -0.5},
            {"t": 1, "x": 900, "y": 300, "depth": 0.8},
        ]}
        pose = evaluate_motion({"_scene_progress": 0.5}, actor, 2.0)
        self.assertGreater(pose["x"], 100)
        self.assertLess(pose["y"], 600)
        self.assertGreater(pose["depth_scale"], 1.0)

    def test_depth_scale_is_clamped(self):
        near = evaluate_motion({"depth": 50}, {}, 0)
        far = evaluate_motion({"depth": -50}, {}, 0)
        self.assertEqual(near["depth_scale"], 1.42)
        self.assertEqual(far["depth_scale"], 0.62)

    def test_turn_and_articulation_controls_survive(self):
        pose = evaluate_motion({"body_angle": 35, "head_angle": -20,
                                "body_lean": 12, "action_progress": 0.7}, {}, 1)
        self.assertEqual(pose["body_angle"], 35)
        self.assertEqual(pose["head_angle"], -20)
        self.assertEqual(pose["body_lean"], 12)
        self.assertEqual(pose["action_progress"], 0.7)

    def test_path_validation_rejects_bad_timing_and_missing_coordinates(self):
        with self.assertRaises(ValueError):
            validate_path_points([{"t": 0, "x": 0, "y": 0},
                                  {"t": 0, "x": 2, "y": 3}])
        with self.assertRaises(ValueError):
            validate_path_points([{"t": 0, "x": 0, "y": 0},
                                  {"t": 1, "x": 2}])


if __name__ == "__main__":
    unittest.main()
