from __future__ import annotations

"""Story-aware 2D camera moves: focus, push-ins, pans and tracking."""
import math
from typing import Any
from PIL import Image

W, H = 1280, 720

def _smooth(a: float, b: float, t: float) -> float:
    u = max(0.0, min(1.0, t))
    u = u*u*(3.0-2.0*u)
    return a + (b-a)*u

def apply_camera(image: Image.Image, scene: dict[str, Any], progress: float) -> Image.Image:
    camera = scene.get("camera") or {}
    if not isinstance(camera, dict):
        camera = {}
    p = max(0.0, min(1.0, float(progress)))
    zoom0 = float(camera.get("zoom_start", 1.0))
    zoom1 = float(camera.get("zoom_end", 1.035))
    zoom = _smooth(zoom0, zoom1, p)
    # Explicit focus coordinates win; otherwise track a requested actor, then
    # use the primary actor as a useful subject-aware default for close shots.
    focus_x = camera.get("focus_x")
    focus_y = camera.get("focus_y")
    target_id = camera.get("focus_actor")
    actors = list(scene.get("actors") or [])
    if scene.get("actor"):
        actors.insert(0, scene["actor"])
    target = next((a for a in actors if target_id and
                   str(a.get("character_id", a.get("id", ""))) == str(target_id)), None)
    if target is None and camera.get("track_subject", False) and actors:
        target = actors[0]
    if target is not None:
        keys = target.get("keyframes") or []
        if keys:
            # Linear interpolation is sufficient for the camera target; actor
            # pose interpolation remains owned by the character renderer.
            left, right = keys[0], keys[-1]
            focus_x = float(left.get("x", 640)) + (float(right.get("x", 640))-float(left.get("x", 640)))*p
            focus_y = float(left.get("y", 610)) + (float(right.get("y", 610))-float(left.get("y", 610)))*p - 90
    fx = float(focus_x if focus_x is not None else 640)
    fy = float(focus_y if focus_y is not None else 360)
    # Pan values remain compatible with the older normalized camera field.
    pan_x = float(camera.get("pan", 0.0)) * W * 0.5 + float(camera.get("pan_x", 0.0))
    pan_y = float(camera.get("pan_y", 0.0))
    if zoom <= 1.0001 and abs(pan_x) < 0.1 and abs(pan_y) < 0.1:
        return image
    nw, nh = max(W, int(W*zoom)), max(H, int(H*zoom))
    enlarged = image.resize((nw, nh), Image.Resampling.LANCZOS)
    cx = int(fx*zoom - W/2 + pan_x)
    cy = int(fy*zoom - H/2 + pan_y)
    cx = max(0, min(nw-W, cx))
    cy = max(0, min(nh-H, cy))
    return enlarged.crop((cx, cy, cx+W, cy+H))
