from __future__ import annotations

"""Small, reusable scene transition compositor."""
from typing import Any
from PIL import Image, ImageDraw, ImageFilter


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def apply_transition(
    current: Image.Image,
    outgoing: Image.Image | None,
    scene: dict[str, Any],
    progress: float,
    first_scene: bool = False,
) -> Image.Image:
    spec = scene.get("transition_in")
    if spec is None and not first_scene:
        return current
    if isinstance(spec, str):
        spec = {"type": spec}
    if not isinstance(spec, dict):
        spec = {}
    kind = str(spec.get("type", "fade" if first_scene else "cross_dissolve")).lower()
    duration = max(0.05, float(spec.get("duration", 0.55)))
    scene_duration = max(0.001, float(scene.get("end", 1.0)) - float(scene.get("start", 0.0)))
    amount = _smooth(min(1.0, max(0.0, progress) * scene_duration / duration))
    if amount >= 1.0:
        return current

    black = Image.new("RGB", current.size, (0, 0, 0))
    if kind in ("fade", "fade_from_black", "dip_to_black"):
        return Image.blend(black, current.convert("RGB"), amount)
    if kind in ("cross_dissolve", "dissolve") and outgoing is not None:
        return Image.blend(outgoing.convert("RGB"), current.convert("RGB"), amount)
    if kind in ("wipe_left", "wipe_right", "wipe_up", "wipe_down") and outgoing is not None:
        width, height = current.size
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        feather = max(2, int(min(width, height) * 0.018))
        if kind == "wipe_left":
            edge = int(width * amount)
            draw.rectangle((0, 0, edge, height), fill=255)
            draw.rectangle((max(0, edge-feather), 0, min(width, edge+feather), height), fill=255)
        elif kind == "wipe_right":
            edge = int(width * (1.0-amount))
            draw.rectangle((edge, 0, width, height), fill=255)
            draw.rectangle((max(0, edge-feather), 0, min(width, edge+feather), height), fill=255)
        elif kind == "wipe_up":
            edge = int(height * amount)
            draw.rectangle((0, 0, width, edge), fill=255)
            draw.rectangle((0, max(0, edge-feather), width, min(height, edge+feather)), fill=255)
        else:
            edge = int(height * (1.0-amount))
            draw.rectangle((0, edge, width, height), fill=255)
            draw.rectangle((0, max(0, edge-feather), width, min(height, edge+feather)), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1, feather // 3)))
        return Image.composite(current.convert("RGB"), outgoing.convert("RGB"), mask)
    # Safe fallback for an unknown transition name.
    if outgoing is not None:
        return Image.blend(outgoing.convert("RGB"), current.convert("RGB"), amount)
    return Image.blend(black, current.convert("RGB"), amount)
