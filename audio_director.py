from __future__ import annotations

"""Scene-grounded sound planning and deterministic fallback sound synthesis.

Groq can replace plan_scene_audio later. The contract is a list of timestamped,
evidence-backed cues; the renderer never guesses a sound from narration alone.
"""
import math
import random
import struct
import wave
from pathlib import Path
from typing import Any

from scene_understanding_agent import analyse_script

SAMPLE_RATE = 22050
ALLOWED_EVENTS = {"door_open", "footsteps", "rain", "wind", "bird_wings", "bird_call"}


def plan_scene_audio(script: dict[str, Any]) -> list[dict[str, Any]]:
    """Infer only cues supported by visible scene/action data."""
    cues: list[dict[str, Any]] = []
    understanding = analyse_script(script)
    scenes = script["scenes"]
    previous_door = 0.0
    for index, scene in enumerate(scenes):
        start, end = float(scene["start"]), float(scene["end"])
        scene_report = understanding["scenes"][index]
        environment = scene.get("environment", "")
        door = float(scene.get("door_open", 0.0))
        if door > previous_door + 0.08:
            cues.append({"event": "door_open", "start": start, "duration": 1.25,
                         "evidence": f"door_open changed {previous_door:.2f}->{door:.2f}",
                         "source": "visual_state"})
        previous_door = door

        actor = scene.get("actor", {})
        keys = actor.get("keyframes", [])
        actor_moves = any(a["moves"] and a["visible"] for a in scene_report["actors"])
        if actor_moves:
            cues.append({"event": "footsteps", "start": start,
                         "duration": max(0.5, end-start),
                         "evidence": "visible actor has walk/run pose and positional movement",
                         "source": "animation_keyframes"})

        # Rain is emitted only when the script explicitly selects a rain environment.
        if environment == "rainroom" or scene.get("weather") == "rain":
            cues.append({"event": "rain", "start": start, "duration": end-start,
                         "evidence": f"environment={environment}; weather={scene.get('weather', 'unspecified')}", "source": "scene_environment"})
        # Wind is allowed only for an explicitly exposed outdoor environment.
        if environment in ("street", "forest") and scene.get("weather") == "wind":
            cues.append({"event": "wind", "start": start, "duration": end-start,
                         "evidence": "outdoor environment with weather=wind",
                         "source": "scene_environment"})
        # Bird sounds require a visible bird actor, never merely an outdoor background.
        visible_bird = any(a["species"] == "bird" and a["visible"] for a in scene_report["actors"])
        if visible_bird:
            cues.append({"event": "bird_wings", "start": start, "duration": 0.8,
                         "evidence": "visible actor species=bird", "source": "character_manifest"})
    return cues


def validate_audio_cues(cues: list[dict[str, Any]], duration: float) -> None:
    for cue in cues:
        if cue.get("event") not in ALLOWED_EVENTS:
            raise ValueError(f"Unsupported sound event: {cue.get('event')}")
        start, length = float(cue["start"]), float(cue["duration"])
        if start < 0 or length <= 0 or start + length > duration + 0.02:
            raise ValueError(f"Audio cue outside video timeline: {cue}")
        if not cue.get("evidence"):
            raise ValueError("Every sound cue must include visual/scene evidence")


def _event_sample(event: str, t: float, rng: random.Random) -> float:
    """Small original procedural foley palette; replaceable by licensed source assets."""
    if event == "door_open":
        # Low hinge groan with a rising/falling metallic overtone.
        envelope = min(1.0, t / 0.12) * max(0.0, 1.0 - t / 1.25)
        freq = 105 + 42 * math.sin(t * 2.1)
        return envelope * (0.19 * math.sin(2*math.pi*freq*t) +
                           0.055 * math.sin(2*math.pi*freq*2.03*t))
    if event == "footsteps":
        phase = t % 0.48
        if phase > 0.13:
            return 0.0
        envelope = math.exp(-phase * 28) * min(1.0, t*5)
        thud = math.sin(2*math.pi*(72-110*phase)*t)
        grit = (rng.random()*2-1) * math.exp(-phase*45)
        return envelope * (0.23*thud + 0.045*grit)
    if event == "rain":
        return (rng.random()*2-1) * 0.055
    if event == "wind":
        slow = 0.55 + 0.45*math.sin(2*math.pi*0.17*t)
        return (rng.random()*2-1) * 0.035 * slow
    if event == "bird_wings":
        pulse = abs(math.sin(2*math.pi*5.2*t)) ** 5
        return pulse * (rng.random()*2-1) * 0.11
    if event == "bird_call":
        return 0.12 * math.sin(2*math.pi*(1150+220*math.sin(t*5))*t) * math.exp(-t*2)
    return 0.0


def render_audio(script: dict[str, Any], output: Path) -> list[dict[str, Any]]:
    duration = float(script["duration"])
    cues = plan_scene_audio(script)
    validate_audio_cues(cues, duration)
    rng = random.Random(20261115)
    total = int(duration * SAMPLE_RATE)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        block = bytearray()
        for n in range(total):
            t = n / SAMPLE_RATE
            sample = 0.0
            for cue in cues:
                local = t - float(cue["start"])
                if 0 <= local <= float(cue["duration"]):
                    # Gentle edges for beds; event sounds keep their natural attack.
                    event = cue["event"]
                    value = _event_sample(event, local, rng)
                    if event in ("rain", "wind"):
                        fade = min(1.0, local*2, max(0.0, (float(cue["duration"])-local)*2))
                        value *= fade
                    sample += value
            sample = max(-0.92, min(0.92, sample))
            packed = struct.pack("<h", int(sample*32767))
            block.extend(packed)
            block.extend(packed)
            if len(block) >= 65536:
                wav.writeframesraw(block)
                block.clear()
        if block:
            wav.writeframesraw(block)
    return cues
