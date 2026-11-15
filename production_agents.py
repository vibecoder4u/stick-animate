from __future__ import annotations

"""Collaborative script-to-animation production agents.

Each agent owns a distinct planning responsibility. The free deterministic
Scene Designer remains the fallback; an optional Groq-compatible model can
replace the creative decisions per script. Model output is always validated.
"""
import copy
from typing import Any

from agent_runtime import AgentUnavailable, FreeLLM
from scene_designer import design_story


class ScriptAnalystAgent:
    def __init__(self, llm: FreeLLM) -> None:
        self.llm = llm

    def analyse(self, story: str, title: str, duration: float) -> dict[str, Any]:
        return self.llm.json_completion(
            "You are the Script Analyst for a 2D animation studio. Return JSON only. "
            "Extract story beats in order, characters with species and traits, explicit locations, "
            "props, actions, emotional turns, and continuity facts. Never invent plot events.",
            f"TITLE: {title}\nDURATION: {duration}\nSCRIPT:\n{story}\n"
            "Return keys: beats (array of objects with text, intent, location, characters, actions, "
            "props, emotion), characters (array), continuity (array).",
            0.2,
        )


class SceneDesignerAgent:
    def __init__(self, llm: FreeLLM) -> None:
        self.llm = llm

    def design(self, story: str, title: str, duration: float, analysis: dict[str, Any]) -> dict[str, Any]:
        return self.llm.json_completion(
            "You are a cinematic 2D animation Scene Designer. Design THIS script, not a reusable "
            "template. Every shot must be justified by its story beat. Create visually distinct "
            "locations when the story changes place; preserve continuity when it does not. Invent "
            "specific, story-relevant set dressing and props, not random decoration. Use varied "
            "shot sizes and motivated camera movement. Return renderer-compatible JSON only. "
            "Canvas is 1280x720 at 24fps. Every scene needs start,end,environment,description,caption,"
            "camera,shot_design. camera needs zoom_start,zoom_end,pan. shot_design needs shot_id,"
            "shot_type,location,visual_focus,primary_action,lighting_mood,continuity_from_previous. "
            "Allowed environments: platform,service_gate,tunnel,trackside,exit,stairwell,street,"
            "rainroom,corridor,forest,ship. If none fits, use corridor but describe unique set dressing "
            "in description and set_design. Do not copy the example railway story.",
            f"TITLE: {title}\nDURATION: {duration}\nSCRIPT:\n{story}\n"
            f"SCRIPT ANALYSIS JSON:\n{analysis}\n"
            "Return keys title,size,fps,duration,scenes. Split the whole runtime into story shots; "
            "include character manifests only when characters are visibly present. No gaps or overlaps.",
            0.55,
        )


class CharacterDirectorAgent:
    def __init__(self, llm: FreeLLM) -> None:
        self.llm = llm

    def direct(self, plan: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        return self.llm.json_completion(
            "You are a character animation director. Refine only character manifests in the supplied "
            "scene plan. Use correct species, age/build/wardrobe/hair/expression, screen position, "
            "facing and meaningful keyframes. Human rigs are not suitable for animals. For unsupported "
            "species, preserve species metadata and do not pretend a human rig is correct. Keyframe t "
            "is normalized 0..1. Return JSON {scenes:[{scene_index,actor,actors}]} only. Keep all "
            "story facts and scene timings unchanged.",
            f"PLAN:\n{plan}\nANALYSIS:\n{analysis}",
            0.3,
        )


class MotionDirectorAgent:
    def __init__(self, llm: FreeLLM) -> None:
        self.llm = llm

    def direct(self, plan: dict[str, Any]) -> dict[str, Any]:
        return self.llm.json_completion(
            "You are a 2D animation motion director. Add scene-specific motion metadata: camera "
            "movement, secondary motion, environmental motion, anticipation, follow-through and "
            "easing. Never change scene timing or story. Return JSON {scenes:[{scene_index,camera,"
            "motion_design,environment_motion}]} only. Motions must fit the actual action and location.",
            f"SCENE PLAN:\n{plan}",
            0.35,
        )


def _validate_plan(plan: dict[str, Any], duration: float) -> None:
    if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list) or not plan["scenes"]:
        raise ValueError("Agent did not return a non-empty scene list")
    plan.setdefault("title", "Untitled Story")
    plan.setdefault("size", [1280, 720])
    plan.setdefault("fps", 24)
    plan["duration"] = float(duration)
    plan["scenes"].sort(key=lambda item: float(item["start"]))
    # Ensure model output covers the entire timeline without overlaps or gaps.
    if abs(float(plan["scenes"][0]["start"])) > 0.02:
        raise ValueError("Agent scene plan must start at zero")
    if abs(float(plan["scenes"][-1]["end"]) - duration) > 0.05:
        raise ValueError("Agent scene plan must end at target duration")
    for scene in plan["scenes"]:
        scene.setdefault("caption", str(scene.get("description", ""))[:92].upper())
        scene.setdefault("environment", "corridor")
        scene.setdefault("camera", {"zoom_start": 1.0, "zoom_end": 1.04, "pan": 0.0})
        scene.setdefault("shot_design", {
            "shot_id": "shot", "shot_type": "medium_action",
            "location": scene["environment"], "visual_focus": "story_action",
            "primary_action": "idle", "lighting_mood": "story_motivated",
            "continuity_from_previous": "preserve_story_continuity",
        })
    # Keep validation independent of the renderer to avoid circular imports.
    previous_end = 0.0
    for index, scene in enumerate(plan["scenes"]):
        start, end = float(scene["start"]), float(scene["end"])
        if start < previous_end - 0.02 or end <= start or end > duration + 0.05:
            raise ValueError(f"Invalid or overlapping timing in scene {index}")
        previous_end = end
        actor = scene.get("actor", {})
        keys = actor.get("keyframes", []) if isinstance(actor, dict) else []
        times = [float(key["t"]) for key in keys]
        if times and (times != sorted(times) or times[0] < 0 or times[-1] > 1):
            raise ValueError(f"Invalid actor keyframes in scene {index}")


def design_production(story: str, duration: float, title: str = "Untitled Story",
                      fps: int = 24, llm: FreeLLM | None = None) -> dict[str, Any]:
    """Run specialist agents; fall back cleanly when free API is unavailable."""
    llm = llm or FreeLLM()
    if not llm.available:
        plan = design_story(story, duration, title, fps)
        plan["design_metadata"].update({
            "pipeline": "multi-agent-compatible-fallback",
            "provider": "none",
            "agents": ["script_analyst_fallback", "scene_designer_fallback",
                       "character_director_fallback", "motion_director_fallback"],
            "creative_mode": "deterministic",
        })
        return plan

    # The deterministic plan is a safe baseline if any creative agent fails.
    fallback = design_story(story, duration, title, fps)
    try:
        analyst = ScriptAnalystAgent(llm)
        designer = SceneDesignerAgent(llm)
        character_director = CharacterDirectorAgent(llm)
        motion_director = MotionDirectorAgent(llm)
        analysis = analyst.analyse(story, title, duration)
        plan = designer.design(story, title, duration, analysis)
        plan.setdefault("fps", fps)
        plan.setdefault("size", [1280, 720])
        character_changes = character_director.direct(plan, analysis).get("scenes", [])
        for change in character_changes:
            index = int(change["scene_index"])
            if 0 <= index < len(plan["scenes"]):
                if "actor" in change:
                    plan["scenes"][index]["actor"] = change["actor"]
                if "actors" in change:
                    plan["scenes"][index]["actors"] = change["actors"]
        motion_changes = motion_director.direct(plan).get("scenes", [])
        for change in motion_changes:
            index = int(change["scene_index"])
            if 0 <= index < len(plan["scenes"]):
                for key in ("camera", "motion_design", "environment_motion"):
                    if key in change:
                        plan["scenes"][index][key] = change[key]
        _validate_plan(plan, duration)
        plan["design_metadata"] = {
            "designer": "multi-agent-production-v1",
            "pipeline": "script_analyst->scene_designer->character_director->motion_director",
            "provider": "groq-compatible",
            "model": llm.model,
            "agents": ["script_analyst", "scene_designer", "character_director", "motion_director"],
            "creative_mode": "ai",
            "scene_count": len(plan["scenes"]),
        }
        return plan
    except (AgentUnavailable, ValueError, TypeError, KeyError) as exc:
        fallback["design_metadata"].update({
            "pipeline": "multi-agent-compatible-fallback",
            "provider": "groq-compatible",
            "creative_mode": "deterministic_fallback",
            "fallback_reason": str(exc),
            "agents": ["script_analyst", "scene_designer", "character_director", "motion_director"],
        })
        return fallback
