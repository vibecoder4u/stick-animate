from __future__ import annotations

"""Script/scene understanding agent with a deterministic, Groq-ready contract.

This first version separates narrative meaning from visible evidence. Narrative text
can suggest what a scene is about, but it cannot by itself authorize a sound effect.
"""
import re
from typing import Any

SCENE_TERMS = {
    "suspense": ("dark", "empty", "silence", "waiting", "behind", "shadow", "unknown", "mystery"),
    "fear": ("fear", "afraid", "terrified", "panic", "horror", "scream"),
    "pursuit": ("follow", "following", "chase", "ran", "running", "escape", "footsteps"),
    "reveal": ("revealed", "appeared", "opened", "behind him", "there it was"),
    "weather": ("rain", "storm", "wind", "thunder", "snow", "fog"),
}
ACTION_POSES = {"walk", "run", "reach", "fear", "crouch", "idle"}


def _words(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", str(value or "").lower()))


def _actor_facts(scene: dict[str, Any]) -> list[dict[str, Any]]:
    actors = []
    candidates = []
    if isinstance(scene.get("actor"), dict):
        candidates.append(scene["actor"])
    candidates.extend(a for a in scene.get("actors", []) if isinstance(a, dict))
    for i, actor in enumerate(candidates):
        keys = actor.get("keyframes", [])
        poses = [str(k.get("pose", "idle")) for k in keys]
        xs = [float(k.get("x", 0)) for k in keys]
        displacement = max(xs) - min(xs) if xs else 0.0
        species = str(actor.get("species", "human"))
        actors.append({
            "actor_index": i,
            "species": species,
            "visible": actor.get("visible", True) is not False,
            "poses": poses,
            "moves": displacement > 18 and any(p in ("walk", "run") for p in poses),
            "horizontal_displacement": round(displacement, 1),
            "explicit_events": list(actor.get("events", [])),
        })
    return actors


def analyse_scene(scene: dict[str, Any], index: int) -> dict[str, Any]:
    start, end = float(scene["start"]), float(scene["end"])
    narration = scene.get("narration", scene.get("voiceover", ""))
    text = " ".join(str(scene.get(k, "")) for k in ("caption", "subcaption", "description", "narration", "voiceover"))
    tokens = _words(text)
    narrative = [label for label, terms in SCENE_TERMS.items() if tokens.intersection(terms)]
    actors = _actor_facts(scene)
    env = str(scene.get("environment", "unspecified"))
    visual_facts = []
    if env != "unspecified":
        visual_facts.append({"fact": "environment", "value": env, "evidence": "scene.environment"})
    if float(scene.get("door_open", 0) or 0) > 0:
        visual_facts.append({"fact": "door_open", "value": float(scene["door_open"]), "evidence": "scene.door_open"})
    for actor in actors:
        if actor["visible"]:
            visual_facts.append({"fact": "visible_actor", "value": actor["species"],
                                 "evidence": f"scene actor manifest #{actor['actor_index']}"})
            if actor["moves"]:
                visual_facts.append({"fact": "locomotion", "value": actor["poses"],
                                     "evidence": f"actor keyframes; displacement={actor['horizontal_displacement']}px"})
    return {
        "scene_index": index,
        "start": start,
        "end": end,
        "duration": end-start,
        "environment": env,
        "narrative_intents": narrative,
        "narrative_text": text,
        "narration_is_sound_evidence": False,
        "visual_facts": visual_facts,
        "actors": actors,
        "sound_decision_policy": "Require visual/action evidence; narrative keywords alone never trigger SFX.",
    }


def analyse_script(script: dict[str, Any]) -> dict[str, Any]:
    """Produce structured scene understanding for the director and future Groq agent."""
    scenes = [analyse_scene(scene, i) for i, scene in enumerate(script["scenes"])]
    themes = sorted({theme for scene in scenes for theme in scene["narrative_intents"]})
    return {
        "agent": "deterministic-script-understanding-v1",
        "title": script.get("title", "Untitled"),
        "duration": float(script["duration"]),
        "overall_themes": themes,
        "scene_count": len(scenes),
        "scenes": scenes,
        "groq_ready_contract": {
            "input": ["script text", "scene descriptions", "environment", "actor manifests", "keyframes"],
            "output": ["scene intent", "visible facts", "character actions", "evidence-backed event proposals"],
            "guardrail": "AI proposals must be validated against structured visual/action evidence.",
        },
    }
