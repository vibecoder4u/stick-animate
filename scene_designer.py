from __future__ import annotations

"""Deterministic multi-shot scene designer.

Turns a plain story into a timed, renderer-compatible shot list. This is a
baseline planner: it creates a visual plan and metadata, not AI-generated art.
A future Groq planner can replace the decisions while keeping this contract.
"""
import re
from typing import Any

ENVIRONMENT_RULES = [
    ("platform", ("railway station", "train station", "platform", "last train", "train")),
    ("service_gate", ("service gate", "locked gate", "staff only", "maintenance door")),
    ("tunnel", ("tunnel", "underground", "subway tunnel")),
    ("trackside", ("railway track", "tracks", "trackside", "train tracks")),
    ("exit", ("exit", "exit door", "fire escape", "outside")),
    ("stairwell", ("stairs", "staircase", "stairwell", "steps")),
    ("street", ("street", "road", "alley", "sidewalk", "city")),
    ("rainroom", ("window", "bedroom", "living room", "apartment", "house", "room")),
    ("corridor", ("hallway", "corridor", "passage", "inside")),
    ("forest", ("forest", "woods", "trees", "jungle")),
    ("ship", ("ship", "boat", "deck", "vessel")),
]
SHOT_TYPES = ("establishing_wide", "medium_action", "close_up", "over_shoulder", "low_angle", "reveal")
FOCUS_RULES = [
    ("train", ("train", "railway", "platform")),
    ("gate", ("gate", "door", "locked")),
    ("tunnel", ("tunnel", "darkness", "underground")),
    ("shadow", ("shadow", "figure", "silhouette", "someone")),
    ("window", ("window", "rain", "glass")),
    ("stairs", ("stairs", "staircase")),
    ("footprints", ("footsteps", "footprints", "ran", "running")),
]

def split_beats(story: str) -> list[str]:
    # Keep short dialogue fragments together; discard empty whitespace.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", story.strip())
    beats = [p.strip() for p in parts if p.strip()]
    if len(beats) == 1 and len(beats[0]) > 260:
        beats = [p.strip() for p in re.split(r"[,;:]\s+", beats[0]) if p.strip()]
    return beats

def _environment(text: str, previous: str | None) -> str:
    lowered = text.lower()
    for env, terms in ENVIRONMENT_RULES:
        if any(term in lowered for term in terms):
            return env
    # If the story does not name a new place, preserve location continuity.
    return previous or "corridor"

def _focus(text: str) -> str:
    lowered = text.lower()
    for focus, terms in FOCUS_RULES:
        if any(term in lowered for term in terms):
            return focus
    return "character_action"

def _species(text: str) -> str | None:
    lowered = text.lower()
    rules = [
        ("dinosaur", ("dinosaur", "t-rex", "trex", "velociraptor")),
        ("dog", ("dog", "puppy", "hound", "wolf")),
        ("cat", ("cat", "kitten", "feline")),
        ("bird", ("bird", "eagle", "owl", "crow", "parrot", "sparrow")),
        ("fish", ("fish", "shark", "whale", "dolphin")),
    ]
    for species, words in rules:
        if any(re.search(r"\b" + re.escape(word) + r"\b", lowered) for word in words):
            return species
    if re.search(r"\b(boy|girl|man|woman|person|he|she|they|someone|human)\b", lowered):
        return "human"
    return None

def _pose(text: str) -> str:
    lowered = text.lower()
    if any(w in lowered for w in ("swam", "swimming", "underwater", "dives")):
        return "swim"
    if any(w in lowered for w in ("flew", "flying", "soared", "flapped", "takes flight")):
        return "fly"
    if any(w in lowered for w in ("ran", "running", "chased", "sprinted", "fled", "escape")):
        return "run"
    if any(w in lowered for w in ("looked back", "turned", "noticed", "saw", "watched")):
        return "look_back"
    if any(w in lowered for w in ("listened", "heard", "whisper", "sound")):
        return "listen"
    if any(w in lowered for w in ("fell", "stumbled", "tripped")):
        return "stumble"
    if any(w in lowered for w in ("afraid", "terrified", "fear", "horror", "shaking")):
        return "fear"
    if any(w in lowered for w in ("walked", "walking", "approached", "entered")):
        return "walk"
    return "idle"

def design_story(story: str, duration: float, title: str = "Untitled Story", fps: int = 24) -> dict[str, Any]:
    """Create multiple timed scenes from plain story text, with varied shot plans."""
    if not story.strip():
        raise ValueError("Story text cannot be empty")
    if duration <= 0 or fps <= 0:
        raise ValueError("Duration and fps must be positive")
    beats = split_beats(story)
    if not beats:
        raise ValueError("No story beats found")
    # Avoid unrenderably tiny shots while retaining every beat.
    if len(beats) > max(1, int(duration // 1.5)):
        merged: list[str] = []
        for i, beat in enumerate(beats):
            if i % 2 == 0 and i + 1 < len(beats):
                merged.append(beat + " " + beats[i + 1])
            elif i % 2 == 1:
                continue
            else:
                merged.append(beat)
        beats = merged
    count = len(beats)
    base = duration / count
    scenes = []
    previous_env = None
    for i, beat in enumerate(beats):
        env = _environment(beat, previous_env)
        previous_env = env
        pose = _pose(beat)
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        focus = _focus(beat)
        # Distinct camera language per shot; renderer supports a restrained push/pan.
        zooms = {
            "establishing_wide": (1.0, 1.025, -0.025),
            "medium_action": (1.005, 1.045, 0.045),
            "close_up": (1.035, 1.09, 0.0),
            "over_shoulder": (1.015, 1.055, -0.05),
            "low_angle": (1.0, 1.04, 0.065),
            "reveal": (1.025, 1.085, -0.07),
        }
        z0, z1, pan = zooms[shot]
        start = round(i * base, 3)
        end = round(duration if i == count - 1 else (i + 1) * base, 3)
        scene: dict[str, Any] = {
            "start": start, "end": end, "environment": env,
            "description": beat,
            "caption": beat.upper()[:92],
            "camera": {"shot_type": shot, "zoom_start": z0, "zoom_end": z1, "pan": pan},
            "shot_design": {
                "shot_id": f"shot-{i+1:03d}", "shot_type": shot,
                "location": env, "visual_focus": focus, "primary_action": pose,
                "lighting_mood": "high_contrast_suspense",
                "continuity_from_previous": "maintain_location" if env == (scenes[-1]["environment"] if scenes else None) else "establish_new_location",
                "variation_rule": "change_composition_or_camera_for_each_beat",
            },
        }
        if any(w in beat.lower() for w in ("rain", "raining", "storm")):
            scene["weather"] = "rain"
        species = _species(beat)
        if pose != "idle" or species:
            scene["actor"] = {
                "species": species or "human",
                "scale": 1.0, "wardrobe": "coat", "hair": "short",
                "expression": "fear" if pose in ("fear", "look_back", "listen") else "neutral",
                "keyframes": [
                    {"t": 0.0, "x": 350 + (i % 3) * 100, "y": 608, "pose": pose, "facing": 1},
                    {"t": 1.0, "x": 390 + (i % 3) * 100, "y": 608, "pose": pose, "facing": 1},
                ],
            }
        scenes.append(scene)
    return {
        "title": title, "size": [1280, 720], "fps": fps, "duration": duration,
        "design_metadata": {
            "designer": "scene-designer-v1",
            "source": "plain_story_text",
            "scene_count": len(scenes),
            "shot_types": [s["shot_design"]["shot_type"] for s in scenes],
            "note": "Procedural shot planning only; visual asset generation and semantic QA remain separate stages.",
        },
        "scenes": scenes,
    }
