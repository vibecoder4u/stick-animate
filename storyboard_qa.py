from __future__ import annotations

"""Heuristic storyboard QA: detect visual repetition before expensive rendering."""
from collections import Counter
from typing import Any


def audit_storyboard(plan: dict[str, Any]) -> dict[str, Any]:
    scenes = plan.get("scenes") or []
    shot_types: list[str] = []
    actions: list[str] = []
    compositions: list[str] = []
    warnings: list[dict[str, str]] = []
    for index, scene in enumerate(scenes):
        camera = scene.get("camera") or {}
        design = scene.get("shot_design") or {}
        direction = scene.get("visual_direction") or {}
        shot = str(camera.get("shot_type") or design.get("shot_type") or "unspecified")
        action = str(direction.get("visible_action") or design.get("primary_action") or "unspecified")
        actors = list(scene.get("actors") or [])
        if isinstance(scene.get("actor"), dict):
            actors.insert(0, scene["actor"])
        actor_ids = sorted(str(a.get("character_id", a.get("id", "human"))) for a in actors)
        positions = []
        for actor in actors:
            keys = actor.get("keyframes") or []
            if keys:
                first = keys[0]
                positions.append(f"{round(float(first.get('x', 640))/80)}:{round(float(first.get('y', 610))/80)}")
        composition = "|".join((shot, ",".join(actor_ids), ",".join(positions)))
        shot_types.append(shot)
        actions.append(action)
        compositions.append(composition)
        if actors and all(
            len(a.get("keyframes") or []) < 2 or
            all(str(k.get("pose", "idle")).lower() in ("idle", "none", "") for k in a.get("keyframes") or [])
            for a in actors
        ):
            warnings.append({"scene": str(index + 1), "code": "static_actor", "message": "Actors have no authored physical action."})
        if len(actors) > 1 and action in ("idle", "unspecified", "talk"):
            warnings.append({"scene": str(index + 1), "code": "weak_interaction", "message": "Multi-character scene may need a clearer physical interaction."})

    repeated = [key for key, count in Counter(compositions).items() if count > 1]
    for signature in repeated:
        indices = [str(i + 1) for i, value in enumerate(compositions) if value == signature]
        warnings.append({"scene": ",".join(indices), "code": "repeated_composition", "message": "Same shot, cast and approximate staging recur."})
    diversity = len(set(actions)) / max(1, len(actions))
    shot_diversity = len(set(shot_types)) / max(1, len(shot_types))
    if len(scenes) >= 4 and diversity < 0.35:
        warnings.append({"scene": "all", "code": "low_action_diversity", "message": "Storyboard uses too few distinct action intents."})
    if len(scenes) >= 4 and shot_diversity < 0.35:
        warnings.append({"scene": "all", "code": "low_shot_diversity", "message": "Storyboard repeats too few camera shot types."})
    return {
        "version": 1,
        "scene_count": len(scenes),
        "action_diversity": round(diversity, 3),
        "shot_diversity": round(shot_diversity, 3),
        "warning_count": len(warnings),
        "warnings": warnings,
        "note": "Heuristic review flags risks; it does not certify visual quality or replace frame inspection.",
    }
