from __future__ import annotations

"""Deterministic multi-shot scene designer.

Turns a plain story into a timed, renderer-compatible shot list. This is a
baseline planner: it creates a visual plan and metadata, not AI-generated art.
A future Groq planner can replace the decisions while keeping this contract.
"""
import re
from typing import Any

ENVIRONMENT_RULES = [
    ("underwater", ("underwater", "under water", "below the surface", "coral reef")),
    ("beach", ("beach", "shore", "seaside", "ocean", "sea", "swimming", "swam", "waves")),
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
        ("monkey", ("monkey", "ape", "chimpanzee", "gorilla")),
        ("turtle", ("turtle", "tortoise")),
        ("bear", ("bear", "grizzly", "black bear")),
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
    if any(w in lowered for w in ("pushed", "push", "moved the tree", "lifted", "together")):
        return "push"
    if any(w in lowered for w in ("picked up", "reached", "handed", "helped", "rescued")):
        return "reach"
    if any(w in lowered for w in ("afraid", "terrified", "fear", "horror", "shaking")):
        return "fear"
    if any(w in lowered for w in ("walked", "walking", "approached", "entered")):
        return "walk"
    return "idle"

def design_story(story: str, duration: float | None = None, title: str = "Untitled Story", fps: int = 24) -> dict[str, Any]:
    """Create multiple timed scenes from plain story text, with varied shot plans."""
    if not story.strip():
        raise ValueError("Story text cannot be empty")
    if (duration is not None and duration <= 0) or fps <= 0:
        raise ValueError("Duration and fps must be positive")
    beats = split_beats(story)
    if not beats:
        raise ValueError("No story beats found")
    # Auto timing retains every beat and weights time by dialogue/action complexity.
    weights = []
    for beat in beats:
        words = len(beat.split())
        lower = beat.lower()
        action = sum(term in lower for term in ("together", "pushed", "rescued", "fell", "storm", "blocked", "rolled", "stuck"))
        dialogue = 1.35 if chr(34) in beat or any(term in lower for term in ("said", "asked", "shouted")) else 1.0
        emotion = 1.4 if any(term in lower for term in ("alone", "laughed", "scared", "thank you", "friends", "kind")) else 1.0
        weights.append(max(2.0, 1.8 + words / 3.8 + action * 1.1) * dialogue * emotion)
    natural_duration = float(duration) if duration is not None else sum(weights)
    if duration is not None:
        weights = [natural_duration / len(beats)] * len(beats)
    # Keep a human protagonist visible across environment-only story beats.
    # Explicit animal species in an individual beat always takes precedence.
    has_human_protagonist = bool(re.search(
        r"\b(he|she|him|her|his|hers|boy|girl|man|woman|person|detective|stranger|traveller|traveler)\b",
        story.lower(),
    ))
    count = len(beats)
    total_weight = sum(weights)
    durations = [natural_duration * weight / total_weight for weight in weights] if duration is None else weights
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
        start = round(sum(durations[:i]), 3)
        end = round(sum(durations[:i + 1]), 3)
        scene: dict[str, Any] = {
            "start": start, "end": end, "environment": env,
            "description": beat,
            "caption": beat.upper()[:92],
            "camera": {"shot_type": shot, "zoom_start": z0, "zoom_end": z1, "pan": pan,
                       "track_subject": shot in ("close_up", "medium_action", "low_angle")},
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
        if species is None and has_human_protagonist:
            species = "human"
        lower_beat = beat.lower()
        if any(word in lower_beat for word in ("apple", "apples", "fruit")):
            scene["props"] = [{"type": "apples", "count": 5, "x": 0.52, "y": 0.83}]
        if any(word in lower_beat for word in ("fallen tree", "tree blocked", "tree blocks", "blocked the road", "moved the tree")):
            scene.setdefault("props", []).append({"type": "fallen_tree", "x": 0.52, "y": 0.79, "length": 570})
        if pose != "idle" or species:
            scene["actor"] = {
                "species": species or "human",
                "character_id": "protagonist" if species == "human" else f"{species}-{i+1}",
                "scale": 1.0, "wardrobe": "coat", "hair": "short",
                "expression": "fear" if pose in ("fear", "look_back", "listen") else "neutral",
                "keyframes": [
                    {"t": 0.0, "x": 350 + (i % 3) * 100, "y": 608, "pose": pose, "facing": 1},
                    {"t": 1.0, "x": 390 + (i % 3) * 100, "y": 608, "pose": pose, "facing": 1},
                ],
            }
        scenes.append(scene)
    return {
        "title": title, "size": [1280, 720], "fps": fps, "duration": natural_duration,
        "design_metadata": {
            "designer": "scene-designer-v1",
            "source": "plain_story_text",
            "scene_count": len(scenes),
            "shot_types": [s["shot_design"]["shot_type"] for s in scenes],
            "note": "Procedural shot planning only; visual asset generation and semantic QA remain separate stages.",
        },
        "scenes": scenes,
    }
