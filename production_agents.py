from __future__ import annotations
"""Story-led production planner. Auto timing is the default."""
import math
from typing import Any
from agent_runtime import AgentUnavailable, FreeLLM
from scene_designer import design_story

def _validate_plan(plan: dict[str, Any], duration: float | None = None, fps: int = 24,
                   duration_mode: str = "auto") -> float:
    if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list) or not plan["scenes"]:
        raise ValueError("AI planner did not return a non-empty scenes array")
    if fps <= 0 or duration_mode not in ("auto", "strict"):
        raise ValueError("Invalid fps or duration mode")
    plan.setdefault("title", "Untitled Story")
    raw_size = plan.get("size", [1280, 720])
    if isinstance(raw_size, dict):
        raw_size = [raw_size.get("width", 1280), raw_size.get("height", 720)]
    if not isinstance(raw_size, (list, tuple)) or len(raw_size) != 2:
        raise ValueError("AI canvas size must be [width, height] or {width, height}")
    try:
        plan["size"] = [int(raw_size[0]), int(raw_size[1])]
    except (TypeError, ValueError) as exc:
        raise ValueError("AI canvas width and height must be numeric") from exc
    if min(plan["size"]) <= 0:
        raise ValueError("AI canvas width and height must be positive")
    plan["fps"] = int(plan.get("fps") or fps)
    try:
        plan["scenes"].sort(key=lambda item: float(item["start"]))
        first = float(plan["scenes"][0]["start"])
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ValueError("AI scenes must contain numeric start/end timestamps") from exc
    if not math.isfinite(first) or abs(first) > 0.5:
        raise ValueError("AI timeline must begin at zero (within 0.5 seconds)")
    for scene in plan["scenes"]:
        scene["start"] = round(float(scene["start"]) - first, 3)
        scene["end"] = round(float(scene["end"]) - first, 3)
    plan["scenes"][0]["start"] = 0.0
    previous = 0.0
    for i, scene in enumerate(plan["scenes"]):
        start, end = float(scene["start"]), float(scene["end"])
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError(f"Invalid timing in scene {i}")
        if start < previous - 0.02:
            raise ValueError(f"Overlapping scenes at scene {i}")
        if start > previous + 0.25:
            raise ValueError(f"Unplanned timeline gap before scene {i}: {start-previous:.3f}s")
        scene["start"] = round(previous, 3)
        previous = end
        scene.setdefault("caption", str(scene.get("description", ""))[:92].upper())
        scene.setdefault("environment", "forest")
        scene.setdefault("camera", {"zoom_start": 1.0, "zoom_end": 1.04, "pan": 0.0})
        scene.setdefault("shot_design", {"shot_id": f"shot-{i+1}", "shot_type": "story_action",
            "location": scene["environment"], "visual_focus": "primary_action",
            "primary_action": "story_specific_action", "lighting_mood": "story_motivated",
            "continuity_from_previous": "preserve_character_and_prop_continuity"})
    natural_duration = round(float(plan["scenes"][-1]["end"]), 3)
    if duration_mode == "strict":
        if duration is None or duration <= 0:
            raise ValueError("Strict duration mode requires a positive duration")
        if abs(natural_duration - duration) > max(0.25, duration * 0.01):
            raise ValueError(f"Strict duration requested {duration:.3f}s but story plan is {natural_duration:.3f}s")
        plan["scenes"][-1]["end"] = float(duration)
        natural_duration = float(duration)
    plan["duration"] = natural_duration
    plan.setdefault("design_metadata", {})
    plan["design_metadata"]["duration_policy"] = duration_mode
    plan["design_metadata"]["natural_duration_seconds"] = natural_duration
    return natural_duration

def design_production(story: str, duration: float | None = None, title: str = "Untitled Story",
                      fps: int = 24, llm: FreeLLM | None = None,
                      duration_mode: str = "auto") -> dict[str, Any]:
    llm = llm or FreeLLM()
    if duration_mode not in ("auto", "strict"):
        raise ValueError("duration_mode must be 'auto' or 'strict'")
    if duration_mode == "strict" and (duration is None or duration <= 0):
        raise ValueError("Strict duration mode requires a positive duration")
    if not llm.available:
        plan = design_story(story, None if duration_mode == "auto" else duration, title, fps)
        if duration_mode == "strict":
            plan["scenes"][-1]["end"] = float(duration)
            plan["duration"] = float(duration)
        plan["design_metadata"].update({"provider": "none", "creative_mode": "deterministic",
            "pipeline": "local-fallback-no-api", "duration_policy": duration_mode,
            "natural_duration_seconds": plan["duration"]})
        return plan
    system = (
        "You are the master preproduction brain of a professional 2D animation studio. "
        "In ONE response produce a complete renderer-ready JSON scene plan for this exact story. "
        "Think like script analyst, scene designer, character director and motion director, but make no extra API calls. "
        "Preserve every named character and correct species. Give each scene concrete visible actions and all present actors "
        "with species, distinct appearance, scale, accent_rgb, wardrobe, expression and normalized keyframes "
        "(t 0..1, x,y,pose,facing). Use multiple actors when interacting. Include story-specific props, environment, "
        "camera, lighting, weather and continuity. No generic repeated scenes; do not invent plot events. "
        "Canvas 1280x720, 24fps. Return JSON only with title,size,fps,duration,scenes. Each scene requires start,end,"
        "environment,description,caption,camera,shot_design; actors is an array of actor manifests. "
        "CRITICAL TIMING: decide natural duration independently for every beat from action complexity, dialogue length, "
        "reaction time, emotional pauses and choreography. Do NOT divide the story evenly. Do NOT compress to an arbitrary "
        "runtime. Include real pauses where drama needs them. Scenes must form one continuous timeline from 0 with no "
        "gaps or overlaps. Set duration to the final scene end. "
        + (f"The requested {duration}s is only a soft reference; ignore it if natural pacing needs more or less time. " if duration else "")
        + "Use story-appropriate locations such as forest, house, road and storm."
    )
    user = f"TITLE: {title}\nDURATION_POLICY: {duration_mode}\nSOFT_TARGET_SECONDS: {duration or 'none'}\nFPS: {fps}\nSCRIPT:\n{story}"
    try:
        plan = llm.json_completion(system, user, 0.35)
        _validate_plan(plan, duration, fps, duration_mode)
        plan["design_metadata"].update({"designer": "groq-master-planner-v2",
            "pipeline": "single-groq-plan->local-specialists->renderer", "provider": "groq",
            "model": llm.model, "creative_mode": "ai", "scene_count": len(plan["scenes"]),
            "api_requests": 1})
        return plan
    except (AgentUnavailable, ValueError, TypeError, KeyError) as exc:
        raise AgentUnavailable(f"AI scene planning failed; deterministic fallback disabled: {exc}") from exc
