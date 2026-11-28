from __future__ import annotations

"""Frame-synchronised animated chart overlays for story scenes.

Charts are authored as scene-local data and drawn directly into each rendered
frame. The API is renderer-independent: a browser/SVG frontend can consume the
same chart manifest later without changing storyboard semantics.
"""
import math
from typing import Any
from PIL import Image, ImageDraw, ImageFont

PALETTE = {
    "cyan": (83, 210, 224), "green": (103, 220, 160),
    "orange": (255, 183, 94), "pink": (239, 132, 177),
    "blue": (112, 157, 255), "white": (241, 246, 252),
    "muted": (145, 164, 185), "grid": (92, 117, 145),
}

def _font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()

def chart_catalog() -> dict[str, Any]:
    return {
        "line": {"description": "Progressively drawn line graph with animated cursor"},
        "bar": {"description": "Bars grow from baseline in sequence"},
        "progress": {"description": "Animated circular progress ring"},
    }

def draw_charts(image: Image.Image, scene: dict[str, Any], local_t: float = 0.5) -> None:
    charts = scene.get("charts") or []
    if not charts:
        return
    w, h = image.size
    canvas = image.convert("RGBA")
    for item in charts:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "line")).lower()
        if kind not in chart_catalog():
            continue
        start = max(0.0, min(1.0, float(item.get("start", 0.0))))
        end = max(start + 0.001, min(1.0, float(item.get("end", 1.0))))
        if local_t < start or local_t > end:
            continue
        p = max(0.0, min(1.0, (local_t - start) / (end - start)))
        reveal = min(1.0, max(0.0, (p - 0.08) / 0.72))
        fade = min(1.0, p / 0.08, (1.0 - p) / 0.08)
        alpha = int(238 * max(0.0, fade) * float(item.get("opacity", 1.0)))
        if alpha <= 0:
            continue
        width = max(220, min(760, int(item.get("width", 520))))
        height = max(150, min(440, int(item.get("height", 300))))
        cx, cy = int(float(item.get("x", .72)) * w), int(float(item.get("y", .48)) * h)
        x0, y0 = cx - width // 2, cy - height // 2
        layer = Image.new("RGBA", (width + 30, height + 70), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        ox, oy = 15, 48
        panel = (ox, oy, ox + width, oy + height)
        d.rounded_rectangle(panel, radius=22, fill=(9, 19, 33, int(alpha * .92)),
                            outline=(111, 146, 174, int(alpha * .72)), width=2)
        title = str(item.get("title", "PROGRESS")).upper()[:42]
        d.text((ox + 22, oy + 13), title, font=_font(17, True), fill=(*PALETTE["white"], alpha))
        plot_l, plot_t = ox + 48, oy + 58
        plot_r, plot_b = ox + width - 24, oy + height - 42
        for i in range(4):
            gy = plot_t + (plot_b - plot_t) * i / 3
            d.line((plot_l, gy, plot_r, gy), fill=(*PALETTE["grid"], int(alpha * .30)), width=1)
        values = [float(v) for v in item.get("values", [8, 14, 23, 36, 52, 72])]
        if not values:
            values = [0, 1]
        labels = [str(v)[:8] for v in item.get("labels", [])]
        color = PALETTE.get(str(item.get("color", "cyan")), PALETTE["cyan"])
        if kind == "progress":
            value = max(0.0, min(100.0, float(item.get("value", values[-1]))))
            radius = min(width, height) * .27
            bx, by = ox + width / 2, oy + height * .59
            d.arc((bx-radius, by-radius, bx+radius, by+radius), 0, 359,
                  fill=(68, 91, 113, alpha), width=22)
            d.arc((bx-radius, by-radius, bx+radius, by+radius), -90,
                  -90 + 360 * value / 100 * reveal, fill=(*color, alpha), width=22)
            txt = f"{int(value * reveal)}%"
            box = d.textbbox((0, 0), txt, font=_font(30, True))
            d.text((bx-(box[2]-box[0])/2, by-18), txt, font=_font(30, True), fill=(*PALETTE["white"], alpha))
        elif kind == "bar":
            maximum = max(max(values), 1.0)
            slot = (plot_r - plot_l) / len(values)
            for i, value in enumerate(values):
                amount = max(0.0, min(1.0, reveal * len(values) - i))
                bar_h = (plot_b - plot_t) * max(0.0, value) / maximum * amount
                left = plot_l + i * slot + slot * .18
                right = plot_l + (i + 1) * slot - slot * .18
                d.rounded_rectangle((left, plot_b-bar_h, right, plot_b), radius=7,
                                    fill=(*color, alpha))
                if i < len(labels):
                    d.text((left, plot_b+9), labels[i], font=_font(11), fill=(*PALETTE["muted"], alpha))
        else:
            maximum = max(max(values), 1.0)
            minimum = min(0.0, min(values))
            span = max(1.0, maximum - minimum)
            points = []
            for i, value in enumerate(values):
                px = plot_l + (plot_r - plot_l) * i / max(1, len(values)-1)
                py = plot_b - (value - minimum) / span * (plot_b - plot_t)
                points.append((px, py))
            segments = max(0, len(points)-1)
            visible = reveal * segments
            whole = int(visible)
            for i in range(whole):
                d.line((points[i], points[i+1]), fill=(*color, alpha), width=6)
            if whole < segments and whole >= 0:
                fraction = visible - whole
                if segments:
                    a, b = points[whole], points[whole+1]
                    tip = (a[0] + (b[0]-a[0])*fraction, a[1] + (b[1]-a[1])*fraction)
                    d.line((a, tip), fill=(*color, alpha), width=6)
                    pulse = 5 + 3 * (0.5 + 0.5 * math.sin(p * math.tau * 3))
                    d.ellipse((tip[0]-pulse, tip[1]-pulse, tip[0]+pulse, tip[1]+pulse),
                              fill=(*PALETTE["white"], alpha), outline=(*color, alpha), width=3)
            for i, (px, py) in enumerate(points):
                if i <= visible:
                    d.ellipse((px-5, py-5, px+5, py+5), fill=(*PALETTE["white"], alpha))
                if i < len(labels):
                    d.text((px-12, plot_b+9), labels[i], font=_font(11), fill=(*PALETTE["muted"], alpha))
        canvas.alpha_composite(layer, (x0-15, y0-48))
    image.paste(canvas.convert("RGB") if image.mode == "RGB" else canvas)
