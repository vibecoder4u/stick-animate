import unittest
from PIL import Image, ImageChops

from chart_library import chart_catalog, draw_charts


class AnimatedChartTests(unittest.TestCase):
    def test_catalog_exposes_line_bar_and_progress(self):
        self.assertEqual(set(chart_catalog()), {"line", "bar", "progress"})

    def test_line_graph_draws_and_animates_over_time(self):
        scene = {"charts": [{"type": "line", "x": .72, "y": .48, "width": 520,
                             "height": 300, "title": "HABITS COMPOUND",
                             "values": [2, 5, 9, 16, 28, 45],
                             "labels": ["1d", "2d", "3d", "4d", "5d", "6d"]}]}
        early = Image.new("RGB", (1280, 720), "black")
        late = early.copy()
        draw_charts(early, scene, .25)
        draw_charts(late, scene, .82)
        self.assertIsNotNone(ImageChops.difference(early, Image.new("RGB", early.size, "black")).getbbox())
        self.assertNotEqual(early.tobytes(), late.tobytes())

    def test_bar_and_progress_charts_render(self):
        for chart in (
            {"type": "bar", "values": [10, 25, 45, 80], "title": "WEEKLY FOCUS"},
            {"type": "progress", "value": 76, "title": "CONSISTENCY"},
        ):
            image = Image.new("RGB", (1280, 720), "black")
            draw_charts(image, {"charts": [chart]}, .7)
            self.assertIsNotNone(ImageChops.difference(image, Image.new("RGB", image.size, "black")).getbbox())

    def test_chart_respects_scene_local_visibility_window(self):
        image = Image.new("RGB", (1280, 720), "black")
        draw_charts(image, {"charts": [{"type": "line", "start": .3, "end": .8}]}, .1)
        self.assertIsNone(ImageChops.difference(image, Image.new("RGB", image.size, "black")).getbbox())


if __name__ == "__main__":
    unittest.main()
