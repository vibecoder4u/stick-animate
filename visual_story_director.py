from __future__ import annotations

"""Script-specific visual direction layered over renderer-ready scene plans.

The director maps each shot to the closest ordered script beat, then supplies
story purpose, actor emotion and camera defaults. It does not invent plot
events or claim that metadata alone makes a rendered video original.
"""
import re
from collections import Counter
from typing import Any

_WORDS = re.compile(r"[a-z0-9']+")
_STOP_WORDS = {
    "about", "after", "again", "against", "also", "because", "before", "being",
    "between", "could", "does", "from", "have", "into", "just", "like", "more",
    "over", "said", "says", "some", "that", "them", "then", "there", "these",
    "they", "this", "through", "their", "under", "very", "were", "what", "when",
    "where", "which", "while", "with", "would", "your",
}
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
    "reach": ("reached", "helped", "rescued", "grabbed"),
    "push": ("pushed", "moved", "dragged", "pulled", "together"),
    "stumble": ("tripped", "stumbled"),
    "look_back": ("noticed", "saw", "watched", "looked back"),
    "listen": ("heard", "listened", "whispered", "whisper", "sound"),
    "jump": ("jumped", "leapt", "leaped"),
    "swim": ("swam", "swimming", "underwater", "dived"),
    "wave": ("waved", "waving", "goodbye", "hello"),
    "point": ("pointed", "pointing", "indicated"),
    "talk": ("talked", "speaking", "explained", "replied", "said"),
    "think": ("thought", "wondered", "considered", "remembered"),
    "celebrate": ("celebrated", "cheered", "rejoiced", "clapped"),
    "comfort": ("comforted", "hugged", "reassured", "consoled"),
    "hand_over": ("handed", "passed", "gave"),
    "pick_up": ("picked up", "lifted", "collected"),
    "open": ("opened", "unlocked", "pulled open"),
    "climb": ("climbed", "climbing", "scrambled"),
    "fall": ("fell", "falling", "collapsed", "dropped down"),
    "sit": ("sat", "sitting", "settled into the chair"),
    "kneel": ("knelt", "kneeling", "got down on one knee"),
    "turn": ("turned", "spun around", "faced"),
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
_RENDERER_EXPRESSIONS = {
    "fear": "fear", "sad": "sad", "happy": "happy", "angry": "angry",
    "surprised": "surprised", "worried": "worried", "thinking": "curious",
}


def split_script_beats(script: str) -> list[str]:
    """Split paragraphs into ordered sentence beats without losing paragraphs."""
    beats: list[str] = []
    for paragraph in (part.strip() for part in str(script or "").splitlines() if part.strip()):
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()]
        beats.extend(sentences or [paragraph])
    return beats


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _tokens(text: str) -> set[str]:
    return {word for word in _WORDS.findall(text.lower()) if len(word) > 2 and word not in _STOP_WORDS}


def _match_beat(description: str, beats: list[str], minimum_index: int) -> tuple[int, str]:
    """Choose the strongest ordered lexical match; avoid first-common-word matches."""
    scene_tokens = _tokens(description)
    if not scene_tokens:
        index = min(minimum_index, len(beats) - 1)
        return index, beats[index]
    candidates = range(min(minimum_index, len(beats) - 1), len(beats))
    scored = []
    for index in candidates:
        beat_tokens = _tokens(beats[index])
        overlap = len(scene_tokens & beat_tokens)
        if overlap:
            precision = overlap / max(1, len(scene_tokens))
            recall = overlap / max(1, len(beat_tokens))
            score = (2 * precision * recall / (precision + recall)) + min(overlap, 4) * 0.015
            scored.append((score, overlap, index))
    if scored:
        _, _, index = max(scored, key=lambda item: (item[0], item[1], -item[2]))
        return index, beats[index]
    index = min(minimum_index, len(beats) - 1)
    return index, beats[index]


def classify_beat(text: str, index: int, total: int) -> dict[str, str]:
    """Return a compact, deterministic narrative reading for one script beat."""
    lowered = text.lower()
    emotion = next((name for name, words in _EMOTIONS.items() if _contains(lowered, words)), "neutral")
    action = next((name for name, words in _ACTIONS.items() if _contains(lowered, words)), "idle")
    if index == 0:
        role = "opening"
    elif any(term in lowered for term in ("because", "therefore", "as a result", "so that")):
        role = "consequence"
    elif any(term in lowered for term in ("discover", "realiz", "reveal", "understood", "found out")):
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
    focus = next((term for term in (
        "door", "gate", "train", "window", "book", "phone", "letter", "tree",
        "road", "water", "bridge", "light", "shadow", "face", "hands",
        "brain", "memory", "habit", "choice", "friend", "family",
    ) if re.search(r"\b" + re.escape(term) + r"s?\b", lowered)), "character_action")
    return {"role": role, "emotion": emotion, "action": action, "focus": focus}


def apply_visual_direction(plan: dict[str, Any], script: str) -> dict[str, Any]:
    """Annotate shots with ordered script intent and camera defaults."""
    scenes = plan.get("scenes") or []
    beats = split_script_beats(script)
    if not scenes or not beats:
        return plan

    scene_summaries: list[str] = []
    directed_roles: list[str] = []
    beat_cursor = 0
    for index, scene in enumerate(scenes):
        description = " ".join(str(scene.get(key, "")) for key in ("description", "caption", "narration", "voiceover"))
        matched_index, beat = _match_beat(description, beats, beat_cursor)
        beat_cursor = min(matched_index + 1, len(beats) - 1)
        intent = classify_beat(beat, matched_index, len(beats))
        role = intent["role"]
        shot_type, zoom_start, zoom_end = _SHOTS[role]

        camera = scene.setdefault("camera", {})
        if not isinstance(camera, dict):
            camera = {}
            scene["camera"] = camera
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
        if isinstance(scene.get("actor"), dict):
            actors.insert(0, scene["actor"])
        renderer_expression = _RENDERER_EXPRESSIONS.get(intent["emotion"])
        applied_actions = 0
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            if renderer_expression and str(actor.get("expression", "neutral")).lower() in ("", "neutral", "none"):
                actor["expression"] = renderer_expression
            keys = actor.get("keyframes") or []
            poses = [str(key.get("pose", "idle")).lower() for key in keys if isinstance(key, dict)]
            if keys and poses and all(pose in ("", "idle", "none") for pose in poses):
                species = str(actor.get("species", "human")).lower()
                action = intent["action"]
                supported = {"walk", "run", "reach", "push", "stumble", "look_back", "listen", "jump", "wave", "point", "talk", "think", "celebrate", "comfort", "hand_over", "pick_up", "open", "climb", "fall", "sit", "kneel", "turn"}
                if species not in {"human", "boy", "girl", "man", "woman", "old_man"}:
                    supported.update({"swim", "fly"})
                if action in supported:
                    for key in keys:
                        if isinstance(key, dict):
                            key["pose"] = action
                    applied_actions += 1

        # Add one story-relevant animated visual aid when the planner did not
        # author an overlay. Keep it away from the main character staging.
        if not scene.get("stickers"):
            lower_beat = beat.lower()
            sticker_id = None
            sticker_label = None
            sticker_rules = (
                (("brain", "memory", "remember", "mind", "neuron", "nervous system"), "brain", "BRAIN"),
                (("learn", "study", "book", "school", "practice", "practise"), "book", "LEARN"),
                (("time", "wait", "later", "before", "after", "hour", "minute"), "clock", "TIME"),
                (("idea", "realize", "realise", "understood", "discover", "thought"), "idea", "IDEA"),
                (("question", "wonder", "why", "how", "uncertain"), "question", "WHY?"),
                (("success", "achieved", "improved", "stronger", "progress", "won"), "check", "PROGRESS"),
                (("love", "care", "friend", "kind", "comfort", "family"), "heart", "CARE"),
                (("rise", "growth", "increase", "stronger", "upward"), "arrow_up", "GROWTH"),
                (("signal", "connection", "connect", "network", "neuron"), "neuron", "SIGNAL"),
            )
            for terms, candidate, label in sticker_rules:
                if any(term in lower_beat for term in terms):
                    sticker_id, sticker_label = candidate, label
                    break
            if sticker_id:
                scene["stickers"] = [{
                    "id": sticker_id, "x": 0.86, "y": 0.28, "size": 142,
                    "text": sticker_label, "start": 0.08, "end": 0.92,
                    "animation": "pop" if index % 2 == 0 else "float",
                }]

        scene["visual_direction"] = {
            "purpose": role,
            "emotional_tone": intent["emotion"],
            "visible_action": intent["action"],
            "dominant_focus": intent["focus"],
            "script_evidence": beat[:240],
            "script_beat_index": matched_index,
            "actors_given_inferred_action": applied_actions,
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
    metadata = plan.setdefault("design_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        plan["design_metadata"] = metadata
    metadata["visual_direction"] = {
        "version": 2,
        "source": "script_derived",
        "beat_count": len(beats),
        "scene_count": len(scenes),
        "role_distribution": dict(counts),
        "scene_intents": scene_summaries,
        "distinct_role_count": len(counts),
        "note": "Direction is derived from this script; it does not certify visual uniqueness or replace render review.",
    }
    return plan
