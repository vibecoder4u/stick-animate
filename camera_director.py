from __future__ import annotations

"""Cinematic, story-aware 2D camera with eased keyframes and subject tracking."""
import math
from typing import Any
from PIL import Image

W, H = 1280, 720


def _ease(value: float, mode: str = "smoothstep") -> float:
    t = max(0.0, min(1.0, float(value)))
    if mode == "linear":
        return t
    if mode == "ease_in":
        return t * t
    if mode == "ease_out":
        return 1.0 - (1.0 - t) ** 2
    if mode == "ease_in_out_cubic":
        return 4 * t ** 3 if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2
    if mode == "ease_out_cubic":
        return 1 - (1 - t) ** 3
    return t * t * (3.0 - 2.0 * t)


def _sample_track(points: list[dict[str, Any]], progress: float) -> dict[str, float]:
    if not points:
        return {}
    ordered = sorted(points, key=lambda p: float(p.get("t", 0.0)))
    if progress <= float(ordered[0].get("t", 0.0)):
        return {k: float(ordered[0][k]) for k in ("x", "y") if k in ordered[0]}
    for left, right in zip(ordered, ordered[1:]):
        a, b = float(left.get("t", 0.0)), float(right.get("t", 1.0))
        if a <= progress <= b:
            u = _ease((progress - a) / max(1e-8, b - a), "smoothstep")
            return {k: float(left[k]) + (float(right[k]) - float(left[k])) * u
                    for k in ("x", "y") if k in left and k in right}
    return {k: float(ordered[-1][k]) for k in ("x", "y") if k in ordered[-1]}


def _sample_camera_keyframes(keyframes: list[dict[str, Any]], progress: float) -> dict[str, Any]:
    if not keyframes:
        return {}
    ordered = sorted(keyframes, key=lambda k: float(k.get("t", 0.0)))
    if progress <= float(ordered[0].get("t", 0.0)):
        return dict(ordered[0])
    for left, right in zip(ordered, ordered[1:]):
        a, b = float(left.get("t", 0.0)), float(right.get("t", 1.0))
        if a <= progress <= b:
            mode = str(left.get("ease", "smoothstep"))
            u = _ease((progress - a) / max(1e-8, b - a), mode)
            result: dict[str, Any] = {}
            for key in set(left) | set(right):
                if key in ("t", "ease"):
                    continue
                if key in left and key in right and isinstance(left[key], (int, float)) and isinstance(right[key], (int, float)):
                    result[key] = float(left[key]) + (float(right[key]) - float(left[key])) * u
                elif key in left:
                    result[key] = left[key]
                else:
                    result[key] = right[key]
            return result
    return dict(ordered[-1])


def _actor_focus(actor: dict[str, Any], progress: float) -> tuple[float, float] | None:
    path = actor.get("path_points")
    if isinstance(path, list) and path:
        point = _sample_track(path, progress)
        if "x" in point and "y" in point:
            return point["x"], point["y"] - 90
    keys = actor.get("keyframes") or []
    if keys:
        point = _sample_track(keys, progress)
        if "x" in point and "y" in point:
            return point["x"], point["y"] - 90
    return None


def apply_camera(image: Image.Image, scene: dict[str, Any], progress: float) -> Image.Image:
    camera = scene.get("camera") or {}
    if not isinstance(camera, dict):
        camera = {}
    p = max(0.0, min(1.0, float(progress)))
    key = _sample_camera_keyframes(camera.get("keyframes") or [], p)
    width, height = image.size

    zoom0 = float(camera.get("zoom_start", camera.get("zoom", 1.0)))
    zoom1 = float(camera.get("zoom_end", zoom0 if "zoom" in camera else 1.035))
    zoom = float(key.get("zoom", _ease(p, str(camera.get("ease", "smoothstep"))) * (zoom1 - zoom0) + zoom0))
    zoom = max(0.65, min(2.5, zoom))

    fx = key.get("focus_x", camera.get("focus_x"))
    fy = key.get("focus_y", camera.get("focus_y"))
    if "x" in key:
        fx = key["x"]
    if "y" in key:
        fy = key["y"]

    target_id = camera.get("focus_actor", camera.get("track_actor"))
    actors = list(scene.get("actors") or [])
    if scene.get("actor"):
        actors.insert(0, scene["actor"])
    target = next((a for a in actors if target_id and
                  str(a.get("character_id", a.get("id", ""))) == str(target_id)), None)
    if target is None and camera.get("track_subject", camera.get("shot_type") in ("close_up", "medium_action", "low_angle")) and actors:
        target = actors[0]
    if target is not None and not ("focus_x" in key or "focus_y" in key or "x" in key or "y" in key):
        tracked = _actor_focus(target, p)
        if tracked:
            fx, fy = tracked

    fx = float(fx if fx is not None else width / 2)
    fy = float(fy if fy is not None else height / 2)
    pan_x = float(key.get("pan_x", camera.get("pan_x", 0.0))) + float(camera.get("pan", 0.0)) * width * 0.5
    pan_y = float(key.get("pan_y", camera.get("pan_y", 0.0)))

    # A very restrained, deterministic handheld texture; disabled unless authored.
    shake = max(0.0, float(camera.get("shake", 0.0)))
    frequency = max(0.1, float(camera.get("shake_frequency", 8.0)))
    shake_x = math.sin(p * frequency * math.tau) * shake
    shake_y = math.sin(p * frequency * math.tau * 1.37 + 0.8) * shake * 0.55
    pan_x += shake_x
    pan_y += shake_y

    if zoom <= 1.0001 and abs(pan_x) < 0.1 and abs(pan_y) < 0.1 and abs(float(key.get("roll", 0.0))) < 0.01:
        return image
    nw, nh = max(width, int(width * zoom)), max(height, int(height * zoom))
    enlarged = image.resize((nw, nh), Image.Resampling.LANCZOS)
    cx = int(fx * zoom - width / 2 + pan_x)
    cy = int(fy * zoom - height / 2 + pan_y)
    cx = max(0, min(nw - width, cx))
    cy = max(0, min(nh - height, cy))
    result = enlarged.crop((cx, cy, cx + width, cy + height))
    roll = float(key.get("roll", camera.get("roll", 0.0)))
    if abs(roll) > 0.01:
        result = result.rotate(roll, resample=Image.Resampling.BICUBIC, center=(width / 2, height / 2))
    return result
