import unittest
from PIL import Image, ImageChops

from camera_director import apply_camera
from environment_animation import render_environment_background, animate_environment
from scene_designer import design_story


class CameraEnvironmentTests(unittest.TestCase):
    def test_story_planner_recognizes_beach_and_swimming(self):
        plan = design_story("The bear reaches the beach. The bear goes swimming in the ocean.")
        self.assertEqual(plan["scenes"][0]["environment"], "beach")
        self.assertEqual(plan["scenes"][1]["environment"], "beach")

    def test_beach_environment_has_animated_water(self):
        scene = {"environment": "beach"}
        base = render_environment_background(Image.new("RGB", (1280, 720)), "beach", scene)
        first = animate_environment(base, "beach", scene, 0.0)
        later = animate_environment(base, "beach", scene, 1.25)
        self.assertEqual(first.size, (1280, 720))
        self.assertIsNotNone(ImageChops.difference(first, later).getbbox())

    def test_camera_tracks_subject_and_changes_framing(self):
        image = Image.new("RGB", (1280, 720), "navy")
        scene = {
            "camera": {"shot_type": "close_up", "zoom_start": 1.0, "zoom_end": 1.2, "track_subject": True},
            "actor": {"character_id": "bear", "keyframes": [
                {"t": 0.0, "x": 300, "y": 600}, {"t": 1.0, "x": 900, "y": 600}
            ]},
        }
        frame_a = apply_camera(image, scene, 0.0)
        frame_b = apply_camera(image, scene, 1.0)
        self.assertEqual(frame_a.size, (1280, 720))
        self.assertEqual(frame_b.size, (1280, 720))
        self.assertIsNotNone(ImageChops.difference(frame_a, frame_b).getbbox())


if __name__ == "__main__":
    unittest.main()
