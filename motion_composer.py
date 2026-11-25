from __future__ import annotations

"""Deterministic procedural motion layers for the reusable human rig.

The scene plan chooses the action; this module adds continuous secondary motion
without changing authored actor positions or requiring extra AI requests.
"""
import math
from typing import Any


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def compose_motion(pose: str, progress: float, seed: int = 0) -> dict[str, float]:
    """Return normalized anticipation, action and follow-through controls."""
    p = max(0.0, min(1.0, float(progress)))
    pose = str(pose or "idle").lower().replace("-", "_")
    phase_offset = (int(seed) % 17) * 0.19
    cycles = {"walk": 2.2, "run": 3.5, "climb": 2.4, "talk": 1.4,
              "wave": 1.3, "idle": 0.65, "think": 0.45, "listen": 0.55}.get(pose, 1.0)
    phase = (p * cycles * math.tau) + phase_offset
    # A brief wind-up, decisive middle, and damped settle.
    anticipation = 1.0 - smoothstep(p / 0.22) if pose in {
        "jump", "push", "reach", "pick_up", "open", "celebrate", "fall"
    } else 0.0
    follow = smoothstep((p - 0.68) / 0.32)
    pulse = math.sin(math.pi * p)
    active = pose in {"walk", "run", "climb"}
    energetic = pose in {"jump", "celebrate", "fall", "push"}
    bob_amp = 2.2 if active else (3.4 if energetic else 0.9)
    bob = math.sin(phase * 2.0) * bob_amp if active else pulse * bob_amp * (1.0-follow)
    lean_map = {"run": 8.0, "walk": 3.0, "push": 13.0, "reach": 5.0,
                "pick_up": 10.0, "fall": 17.0, "listen": -3.0, "think": -2.0}
    lean = lean_map.get(pose, 0.0) * (1.0 - 0.35 * follow)
    if pose in {"jump", "celebrate"}:
        lean -= 3.0 * pulse
    arm = math.sin(phase) * (0.22 if pose in {"idle", "think", "listen"} else 1.0)
    head = math.sin(phase * 0.7 + 0.8) * (1.8 if pose in {"idle", "think", "listen", "talk"} else 0.8)
    return {
        "phase": phase, "body_bob": bob, "torso_lean": lean,
        "arm_swing": arm, "head_bob": head,
        "anticipation": anticipation, "follow_through": follow,
        "gesture": pulse * (1.0-follow * 0.35),
    }


def motion_for_actor(actor: dict[str, Any], progress: float) -> dict[str, float]:
    keys = actor.get("keyframes") or []
    pose = str(keys[0].get("pose", "idle")) if keys else "idle"
    seed_text = str(actor.get("character_id", actor.get("id", "actor")))
    seed = sum(ord(char) for char in seed_text)
    return compose_motion(pose, progress, seed)
