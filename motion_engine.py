"""Reusable timeline motion helpers for character root paths and depth staging."""
from __future__ import annotations
import math
from typing import Any


def _smooth(u: float) -> float:
    return u*u*(3.0-2.0*u)


def evaluate_motion(pose: dict[str, Any], actor: dict[str, Any], global_t: float) -> dict[str, Any]:
    """Resolve optional path/depth/turn controls without changing legacy scripts.

    path_points: [{t:0..1, x, y, depth?}] in scene-local normalized time.
    depth is a relative camera-plane value (-1 far, +1 near).
    turn_angle/body_angle are degrees; gait_phase can synchronize locomotion.
    """
    out = dict(pose)
    points = actor.get("path_points") or pose.get("path_points")
    if isinstance(points, list) and len(points) >= 2:
        p = max(0.0, min(1.0, float(pose.get("_scene_progress", 0.0))))
        for a, b in zip(points, points[1:]):
            ta, tb = float(a.get("t", 0)), float(b.get("t", 1))
            if ta <= p <= tb:
                u = _smooth((p-ta)/max(1e-8, tb-ta))
                for key in ("x", "y", "depth"):
                    if key in a and key in b:
                        out[key] = float(a[key]) + (float(b[key])-float(a[key]))*u
                break
    depth = max(-1.0, min(1.0, float(out.get("depth", 0.0))))
    out["depth"] = depth
    out["depth_scale"] = max(0.62, min(1.42, 1.0 + depth*0.42))
    out["body_angle"] = float(out.get("body_angle", 0.0))
    out["head_angle"] = float(out.get("head_angle", 0.0))
    if "gait_phase" in out:
        out["gait_phase"] = float(out["gait_phase"])
    out["action_progress"] = max(0.0, min(1.0, float(out.get("action_progress", 0.0))))
    return out


def validate_path_points(points: Any) -> None:
    if points is None:
        return
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("path_points must contain at least two points")
    times = [float(p["t"]) for p in points]
    if any(b <= a for a, b in zip(times, times[1:])) or times[0] < 0 or times[-1] > 1:
        raise ValueError("path_points times must be strictly increasing within 0..1")
    for point in points:
        if "x" not in point or "y" not in point:
            raise ValueError("Each path point requires x and y")
