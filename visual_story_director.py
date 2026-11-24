from __future__ import annotations

"""Script-specific visual direction layered over renderer-ready scene plans.

This module does not invent plot events or assets. It extracts narrative intent
from the supplied script and gives each existing scene a distinct visual job.
The output is deliberately renderer-compatible: it only adjusts supported
camera defaults and actor expressions, while keeping a traceable script link.
"""
import re
from collections import Counter
from typing import Any

_WORDS = re.compile(r"[a-z0-9']+")
_EMOTIONS = {
    "fear": ("afraid", "fear", "terrified", "scared", "panic", "danger", "threat"),
    "sad": ("sad", "grief", "lost", "lonely", "cry", "regret", "heartbroken"),
    "happy": ("happy", "joy", "laughed", "celebrate", "relief", "smiled", "hope"),
    "angry": ("angry", "furious", "argued", "shouted", "rage", "betrayed"),
    "surprised": ("suddenly", "surprised", "shocked", "unexpected", "discovered", "realized"),
    "worried": ("worried", "uncertain", "doubt", "hesitated", "nervous"),
    "thinking": ("thought", "wondered", "considered", "remembered", "understood"),
}
_ACTIONS = {
    "run": ("ran", "running", "sprinted", "chased", "escaped", "fled"),
    "walk": ("walked", "approached", "entered", "left", "crossed", "travelled", "traveled"),
    "reach": ("reached", "picked up", "handed", "helped", "rescued", "grabbed"),
    "push": ("pushed", "lifted", "moved", "dragged", "pulled", "together"),
    "stumble": ("fell", "tripped", "stumbled", "dropped"),
    "look_back": ("noticed", "saw", "watched", "looked back", "turned"),
    "listen": ("heard", "listened", "whispered", "whisper", "sound"),
    "jump": ("jumped", "leapt", "leaped"),
    "swim": ("swam", "swimming", "underwater", "dived"),
}
_SHOTS = {
    "opening": ("establishing_wide", 1.0, 1.045),
    "action": ("medium_action", 1.01, 1.075),
    "emotion": ("close_up", 1.035, 1.10),
    "discovery": ("reveal", 1.02, 1.09),
    "interaction": ("over_shoulder", 1.01, 1.065),
    "consequence": ("low_angle", 1.0, 1.055),
    "reflection": ("close_up", 1.025, 1.075),
}


def split_script_beats(script: str) -> list[str]:
    """Split paragraphs into sentence beats without losing paragraph boundaries."""
    beats: list[str] = []
    for paragraph in (p.strip() for p in script.splitlines() if p.strip()):
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", paragraph) if s.strip()]
        beats.extend(sentences or [paragraph])
    return beats


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def classify_beat(text: str, index: int, total: int) -> dict[str, str]:
    """Return a compact, deterministic narrative reading for one script beat."""
    lowered = text.lower()
    emotion = next((name for name, words in _EMOTIONS.items() if _contains(lowered, words)), "neutral")
    action = next((name for name, words in _ACTIONS.items() if _contains(lowered, words)), "idle")
    if index == 0:
        role = "opening"
    elif any(term in lowered for term in ("because", "therefore", "as a result", "so that")):
        role = "consequence"
    elif any(term in lowered for term in ("realized", "discovered", "revealed", "understood", "found out")):
        role = "discovery"
    elif any(term in lowered for term in ("together", "helped", "handed", "asked", "replied", "said", "told")):
        role = "interaction"
    elif emotion != "neutral" and action in ("idle", "listen", "look_back"):
        role = "emotion"
    elif action != "idle":
        role = "action"
    elif index == total - 1:
        role = "reflection"
    else:
        role = "action"
    if index == total - 1 and role == "opening":
        role = "reflection"
    focus = next((term for term in (
        "door", "gate", "train", "window", "book", "phone", "letter", "tree",
        "road", "water", "bridge", "light", "shadow", "face", "hands",
        "brain", "memory", "habit", "choice", "friend", "family",
    ) if re.search(r"\\b" + re.escape(term) + r"s?\\b", lowered)), "character_action")
    return {"role": role, "emotion": emotion, "action": action, "focus": focus}


def apply_visual_direction(plan: dict[str, Any], script: str) -> dict[str, Any]:
    """Annotate every planned shot with script-derived intent and useful camera defaults."""
    scenes = plan.get("scenes") or []
    beats = split_script_beats(script)
    if not scenes or not beats:
        return plan

    scene_summaries: list[str] = []
    directed_roles: list[str] = []
    for index, scene in enumerate(scenes):
        description = " ".join(str(scene.get(k, "")) for k in ("description", "caption", "narration"))
        # Prefer the scene's own script wording; map to the nearest beat when the
        # AI has paraphrased it, keeping order as a stable fallback.
        beat = beats[min(index, len(beats) - 1)]
        if description:
            candidate = next((b for b in beats if any(
                token in description.lower() for token in _WORDS.findall(b.lower()) if len(token) > 5
            )), None)
            beat = candidate or beat
        intent = classify_beat(beat, min(index, len(beats) - 1), len(beats))
        role = intent["role"]
        shot_type, zoom_start, zoom_end = _SHOTS[role]
        camera = scene.setdefault("camera", {})
        if not isinstance(camera, dict):
            camera = {}
            scene["camera"] = camera
        # Preserve explicit creative camera choices; fill generic/incomplete plans.
        if not camera.get("shot_type") or camera.get("shot_type") in ("story_action", "default"):
            camera["shot_type"] = shot_type
        camera.setdefault("zoom_start", zoom_start)
        camera.setdefault("zoom_end", zoom_end)
        camera.setdefault("pan", (-0.055 if index % 2 else 0.045) if role in ("action", "interaction") else 0.0)
        camera.setdefault("track_subject", role in ("action", "emotion", "interaction"))
        shot_design = scene.setdefault("shot_design", {})
        if isinstance(shot_design, dict):
            shot_design.setdefault("narrative_role", role)
            shot_design.setdefault("visual_focus", intent["focus"])
            shot_design.setdefault("primary_action", intent["action"])
            shot_design.setdefault("emotional_tone", intent["emotion"])
            shot_design.setdefault("script_beat", beat[:240])
        actors = list(scene.get("actors") or [])
        if scene.get("actor"):
            actors.insert(0, scene["actor"])
        if intent["emotion"] != "neutral":
            for actor in actors:
                if str(actor.get("expression", "neutral")).lower() in ("", "neutral", "none"):
                    actor["expression"] = intent["emotion"]
        scene["visual_direction"] = {
            "purpose": role,
            "emotional_tone": intent["emotion"],
            "visible_action": intent["action"],
            "dominant_focus": intent["focus"],
            "script_evidence": beat[:240],
            "composition_note": {
                "opening": "establish the place and spatial relationships",
                "action": "make the physical action readable in silhouette",
                "emotion": "prioritize face, gesture and reaction",
                "discovery": "direct attention toward the newly understood detail",
                "interaction": "show both participants and the object or gesture connecting them",
                "consequence": "show the visible result of the preceding choice or action",
                "reflection": "give the final idea or emotional change room to register",
            }[role],
        }
        scene_summaries.append(role + ":" + intent["focus"])
        directed_roles.append(role)

    counts = Counter(directed_roles)
    plan.setdefault("design_metadata", {})
    plan["design_metadata"]["visual_direction"] = {
        "version": 1,
        "source": "script_derived",
        "beat_count": len(beats),
        "scene_count": len(scenes),
        "role_distribution": dict(counts),
        "scene_intents": scene_summaries,
        "distinct_role_count": len(counts),
        "note": "Direction is derived from this script; it does not certify visual uniqueness or replace render review.",
    }
    return plan
