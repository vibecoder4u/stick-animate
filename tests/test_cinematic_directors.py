import unittest
from PIL import Image
from camera_director import apply_camera
from transition_director import apply_transition


class CinematicDirectorTests(unittest.TestCase):
    def test_camera_keyframes_ease_zoom_and_focus(self):
        image = Image.new("RGB", (1280, 720), "navy")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        draw.rectangle((120, 100, 380, 500), fill="orange")
        draw.rectangle((850, 180, 1120, 600), fill="cyan")
        scene = {"camera": {"keyframes": [
            {"t": 0, "focus_x": 640, "focus_y": 360, "zoom": 1.0},
            {"t": 1, "focus_x": 800, "focus_y": 330, "zoom": 1.2}
        ]}}
        frame = apply_camera(image, scene, 0.5)
        self.assertEqual(frame.size, image.size)
        self.assertNotEqual(frame.tobytes(), image.tobytes())

    def test_camera_tracks_actor_path(self):
        image = Image.new("RGB", (1280, 720), "navy")
        scene = {"actors": [{"id": "hero", "path_points": [
            {"t": 0, "x": 200, "y": 600}, {"t": 1, "x": 1000, "y": 500}
        ]}], "camera": {"focus_actor": "hero", "zoom_start": 1.1, "zoom_end": 1.1}}
        frame = apply_camera(image, scene, 0.5)
        self.assertEqual(frame.size, image.size)

    def test_cross_dissolve_blends_outgoing_and_incoming(self):
        outgoing = Image.new("RGB", (32, 32), "black")
        incoming = Image.new("RGB", (32, 32), "white")
        scene = {"start": 0, "end": 2, "transition_in": {"type": "cross_dissolve", "duration": 1}}
        frame = apply_transition(incoming, outgoing, scene, 0.25)
        pixel = frame.getpixel((16, 16))
        self.assertGreater(pixel[0], 0)
        self.assertLess(pixel[0], 255)

    def test_first_scene_fades_up_from_black(self):
        incoming = Image.new("RGB", (32, 32), "white")
        scene = {"start": 0, "end": 2, "transition_in": {"type": "fade", "duration": 1}}
        frame = apply_transition(incoming, None, scene, 0.25, first_scene=True)
        self.assertGreater(frame.getpixel((10, 10))[0], 0)
        self.assertLess(frame.getpixel((10, 10))[0], 255)


if __name__ == "__main__":
    unittest.main()
