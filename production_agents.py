from __future__ import annotations

"""One-call story planner. Specialist execution remains local and deterministic."""
from typing import Any
from agent_runtime import AgentUnavailable, FreeLLM
from scene_designer import design_story

def _validate_plan(plan: dict[str, Any], duration: float, fps: int) -> None:
    if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list) or not plan["scenes"]:
        raise ValueError("AI planner did not return a non-empty scenes array")
    plan.setdefault("title", "Untitled Story")
    plan.setdefault("size", [1280, 720])
    plan.setdefault("fps", fps)
    plan["duration"] = float(duration)
    plan["scenes"].sort(key=lambda item: float(item["start"]))
    if abs(float(plan["scenes"][0]["start"])) > 0.02:
        raise ValueError("AI plan must start at zero")
    if abs(float(plan["scenes"][-1]["end"]) - duration) > 0.05:
        raise ValueError("AI plan must end at target duration")
    previous = 0.0
    for i, scene in enumerate(plan["scenes"]):
        start, end = float(scene["start"]), float(scene["end"])
        if start < previous - 0.02 or end <= start or end > duration + 0.05:
            raise ValueError(f"Invalid or overlapping timing in scene {i}")
        previous = end
        scene.setdefault("caption", str(scene.get("description", ""))[:92].upper())
        scene.setdefault("environment", "forest")
        scene.setdefault("camera", {"zoom_start": 1.0, "zoom_end": 1.04, "pan": 0.0})
        scene.setdefault("shot_design", {"shot_id": f"shot-{i+1}", "shot_type": "story_action",
            "location": scene["environment"], "visual_focus": "primary_action",
            "primary_action": "story_specific_action", "lighting_mood": "story_motivated",
            "continuity_from_previous": "preserve_character_and_prop_continuity"})

def design_production(story: str, duration: float, title: str = "Untitled Story",
                      fps: int = 24, llm: FreeLLM | None = None) -> dict[str, Any]:
    llm = llm or FreeLLM()
    if not llm.available:
        plan = design_story(story, duration, title, fps)
        plan["design_metadata"].update({"provider": "none", "creative_mode": "deterministic",
            "pipeline": "local-fallback-no-api"})
        return plan
    system = (
        "You are the master preproduction brain of a professional 2D animation studio. "
        "In ONE response produce a complete renderer-ready JSON scene plan for this exact story. "
        "Think internally like a script analyst, scene designer, character director and motion director, "
        "but do not make separate agent/API calls. Preserve every named character and correct species. "
        "Give each scene concrete visible actions, all present actors with species, distinct appearance, "
        "scale, accent_rgb, wardrobe, expression and normalized keyframes (t 0..1, x,y,pose,facing). "
        "Use multiple actors when interacting. Include story-specific props, environment, camera, "
        "lighting mood, weather/environment motion and continuity. Use concise descriptions. "
        "No generic repeated scenes. Do not invent plot events. Canvas 1280x720, 24fps. "
        "Return JSON only with title,size,fps,duration,scenes. Each scene requires start,end,environment,"
        "description,caption,camera,shot_design; actors is an array of actor manifests. "
        "Split timeline evenly across meaningful story beats, no gaps or overlaps. "
        "Use environments such as forest, house, road, cave, beach, city, storm, interior as appropriate."
    )
    user = f"TITLE: {title}\nDURATION_SECONDS: {duration}\nFPS: {fps}\nSCRIPT:\n{story}"
    try:
        plan = llm.json_completion(system, user, 0.35)
        _validate_plan(plan, duration, fps)
        plan["design_metadata"] = {"designer": "groq-master-planner-v1",
            "pipeline": "single-groq-plan->local-specialists->renderer", "provider": "groq",
            "model": llm.model, "creative_mode": "ai", "scene_count": len(plan["scenes"]),
            "api_requests": 1}
        return plan
    except (AgentUnavailable, ValueError, TypeError, KeyError) as exc:
        # Never disguise a failed AI run as successful creative generation.
        raise AgentUnavailable(f"AI scene planning failed; deterministic fallback disabled: {exc}") from exc
