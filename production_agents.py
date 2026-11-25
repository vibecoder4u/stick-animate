from __future__ import annotations
"""Story-led production planner. Auto timing is the default."""
import json
import math
import re
from typing import Any
from agent_runtime import AgentUnavailable, FreeLLM
from scene_designer import design_story
from capability_registry import capability_profile
from visual_story_director import apply_visual_direction
from storyboard_qa import audit_storyboard

def _validate_plan(plan: dict[str, Any], duration: float | None = None, fps: int = 24,
                   duration_mode: str = "auto", story: str | None = None) -> float:
    if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list) or not plan["scenes"]:
        raise ValueError("AI planner did not return a non-empty scenes array")
    if story:
        # Split on sentence boundaries, not newlines: manual workflow input is often one paragraph.
        beats = [part.strip() for part in re.split(r"(?<=[.!?])\s+", story.strip()) if part.strip()]
        words = re.findall(r"[a-z0-9']+", story.lower())
        scene_count = len(plan["scenes"])
        paragraphs = [part.strip() for part in story.splitlines() if part.strip()]
        if len(paragraphs) > 1 and scene_count < len(paragraphs):
            raise ValueError(
                f"Story coverage incomplete: {len(paragraphs)} script paragraphs require at least "
                f"{len(paragraphs)} scenes; planner returned {scene_count}."
            )
        if len(words) >= 40:
            required_scenes = max(8, math.ceil(min(len(beats), 24) * 0.45))
            if scene_count < required_scenes:
                raise ValueError(
                    f"Story coverage incomplete: {len(words)} words across {len(beats)} sentence beats "
                    f"require at least {required_scenes} distinct shots; planner returned {scene_count}. "
                    "Storyboard the actual events and interactions instead of summarizing the script."
                )
        scene_text = " ".join(str(scene.get(key, "")) for scene in plan["scenes"]
                              for key in ("description", "caption", "narration", "voiceover", "actors", "actor"))
        lowered = scene_text.lower()
        event_groups = [
            (("apple", "apples"), ("apple", "apples")),
            (("trip", "tripped", "fell", "fall"), ("trip", "tripped", "fell", "fall")),
            (("monkey", "milo"), ("monkey", "milo")),
            (("turtle", "tia"), ("turtle", "tia")),
            (("storm", "thunder", "rain"), ("storm", "thunder", "rain")),
            (("tree", "fallen tree"), ("tree",)),
            (("bear", "bruno"), ("bear", "bruno")),
            (("push", "pushed", "move", "moved", "lift"), ("push", "move", "lift")),
        ]
        for triggers, evidence in event_groups:
            if any(term in story.lower() for term in triggers) and not any(term in lowered for term in evidence):
                raise ValueError(f"Story coverage incomplete: scene plan omitted this event: {triggers[0]}")
        for match in re.finditer(r"\b([A-Z][a-z]+)\s+the\s+(Monkey|Turtle|Bear|Dog|Cat|Bird|Dinosaur)\b", story):
            name, species = match.group(1).lower(), match.group(2).lower()
            if name not in lowered and species not in lowered:
                raise ValueError(f"Story coverage incomplete: missing character {match.group(1)} the {match.group(2)}")
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
        apply_visual_direction(plan, story)
        plan.setdefault("design_metadata", {})["visual_quality"] = audit_storyboard(plan)
        if duration_mode == "strict":
            plan["scenes"][-1]["end"] = float(duration)
            plan["duration"] = float(duration)
        plan["design_metadata"].update({"provider": "none", "creative_mode": "deterministic",
            "pipeline": "local-fallback-no-api", "duration_policy": duration_mode,
            "natural_duration_seconds": plan["duration"]})
        return plan
    capabilities = capability_profile()
    capability_context = json.dumps(capabilities, sort_keys=True)
    system = (
        "You are the master preproduction brain of a professional 2D animation studio. "
        "In ONE response produce a complete renderer-ready JSON scene plan for this exact story. "
        "Think like script analyst, scene designer, character director and motion director, but make no extra API calls. " +
        "STORY VISUAL DIRECTION: storyboard scenes as purposeful film shots rather than character lineup illustrations. " +
        "For each shot, define foreground/background separation, staging (left/center/right and near/far), subject gaze, " +
        "clear silhouette, readable physical interaction with props, and a single dominant visual focus. " +
        "Vary shot types across establishing wide, two-shot, over-shoulder, medium, close-up and reaction shots " +
        "when motivated by the story. Avoid repeating the same centered full-body composition. " +
        "Animate actions as phases with anticipation, action, follow-through and settling; avoid teleporting between poses. " "Use the procedural gesture vocabulary when the story supports it: wave, point, talk, think, celebrate, comfort, hand_over, pick_up, open, climb, fall, sit, kneel and turn, in addition to walk, run, reach, push, stumble and jump. " +
        "Do not assign the same pose to every keyframe when an action has phases: use a preparatory pose, active pose and recovery pose with smoothly interpolated numeric controls. " +
        "Vary the actor silhouette through arm height, elbow bend, torso lean, head angle, stance width, facing and gaze; avoid repeated neutral standing. " +
        "For interactions, specify both participants and the connecting prop or hand contact; use complementary poses rather than mirrored idle poses. " + +
        "Give walking keyframes continuous travel and believable facing; characters not moving should have subtle idle " +
        "poses, not stiff mannequin poses. Use concrete expressive poses, actor-to-actor eyelines, and scene-specific " +
        "camera focus. Do not replace physical action with captions or stickers. "
        "Preserve every named character and correct species. Give each scene concrete visible actions and all present actors "
        "with species, distinct appearance, scale, accent_rgb, wardrobe, expression and normalized keyframes "
        "(t 0..1, x,y,pose,facing). Use multiple actors when interacting. Include story-specific props, environment, "
        "camera, lighting, weather and continuity. No generic repeated scenes; do not invent plot events. Treat every non-empty script paragraph as a distinct narrative unit: give each paragraph at least one dedicated scene, and split paragraphs containing multiple consequential actions into multiple shots. Never summarize several paragraphs into one montage or skip dialogue-driven interactions. Preserve event order and show the actual action, not merely a caption. "
        "Use ONLY these approved human character_id values for human actors: man_1, man_2, man_3, woman_1, woman_2, child_5 (age 5), child_9 (age 9), child_13 (age 13). " +
        "Choose child IDs by the script's stated age; preserve the visual profile and do not invent a ninth human identity. " +
        "Use actor fields character_id, expression, wardrobe, hair and keyframes. Older people may be an adult identity with age_variant='elderly'. " +
        "Each scene may include a stickers array; each sticker has id,x,y,size,text,start,end. Supported sticker IDs: idea, question, exclamation, brain, book, clock, arrow_up, check, sparkles, heart, neuron, magnify. " +
        "Use stickers only when they explain or emphasize narration; use normalized x/y from 0 to 1 and scene-local start/end from 0 to 1. " +
        "Animals and non-human special characters are NOT part of the default cast; do not add them unless the script plan explicitly contains approved_special_characters metadata. " +
        "Canvas 1280x720, 24fps. For scripts over 60 words create at least 8 distinct shots, and generally "
        "at least one shot for every two sentence beats. Give each shot a specific visible action, not just an "
        "establishing description. Preserve named characters, species, props and major events (apples, falls, rescues, "
        "storms, obstacles and group actions). Do not omit the ending or moral. Return JSON only with title,size,fps,duration,scenes. Each scene requires start,end,"
        "environment,description,caption,camera,shot_design; actors is an array of actor manifests. "
        "CRITICAL TIMING: decide natural duration independently for every beat from action complexity, dialogue length, "
        "reaction time, emotional pauses and choreography. Do NOT divide the story evenly. Do NOT compress to an arbitrary "
        "runtime. Include real pauses where drama needs them. Scenes must form one continuous timeline from 0 with no "
        "gaps or overlaps. Set duration to the final scene end. "
        + (f"The requested {duration}s is only a soft reference; ignore it if natural pacing needs more or less time. " if duration else "")
        + "Use story-appropriate locations such as forest, house, road and storm. " +
        "AUTHORITATIVE RENDERER CAPABILITIES: " + capability_context + " " +
        "Never claim unsupported features. If a required species is unsupported, preserve its identity in the character description, mark renderer_approximation=true, and add a capability warning. " +
        "Only call an environment animated if it appears in animated_backgrounds. For base-plate-only locations, describe the setting precisely but do not promise environmental motion. " +
        "Choose actions and camera controls only from the listed capabilities."
    )
    user = f"TITLE: {title}\nDURATION_POLICY: {duration_mode}\nSOFT_TARGET_SECONDS: {duration or 'none'}\nFPS: {fps}\nSCRIPT:\n{story}"
    try:
        plan = llm.json_completion(system, user, 0.35)
        _validate_plan(plan, duration, fps, duration_mode, story)
        apply_visual_direction(plan, story)
        plan["design_metadata"].update({"designer": "groq-master-planner-v2",
            "pipeline": "single-groq-plan->local-specialists->renderer", "provider": "groq",
            "model": llm.model, "creative_mode": "ai", "scene_count": len(plan["scenes"]),
            "api_requests": 1, "capability_registry_version": capabilities["schema_version"],
            "capability_profile": capabilities, "capability_warnings": []})
        return plan
    except (AgentUnavailable, ValueError, TypeError, KeyError) as exc:
        # Recover specifically from an under-storyboarded AI outline by expanding the
        # original script locally, beat by beat. Do not silently use this path for
        # malformed renderer schemas or unrelated programming errors.
        if isinstance(exc, ValueError) and "Story coverage incomplete" in str(exc):
            recovery = design_story(story, None if duration_mode == "auto" else duration,
                                    title, fps)
            _validate_plan(recovery, duration, fps, duration_mode, story)
            apply_visual_direction(recovery, story)
        recovery.setdefault("design_metadata", {})["visual_quality"] = audit_storyboard(recovery)
            recovery["design_metadata"].update({
                "designer": "groq-outline-local-storyboard-recovery",
                "provider": "groq+local",
                "model": llm.model,
                "creative_mode": "hybrid_storyboard_recovery",
                "pipeline": "single-groq-outline->local-beat-expansion->renderer",
                "recovery_reason": str(exc),
                "api_requests": 1,
                "scene_count": len(recovery["scenes"]),
            })
            return recovery
        raise AgentUnavailable(f"AI scene planning failed; deterministic fallback disabled: {exc}") from exc
