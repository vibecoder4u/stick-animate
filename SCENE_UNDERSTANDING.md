# Script and scene understanding agent

`scene_understanding_agent.py` is the first scene-understanding worker. It runs locally
inside the GitHub Actions render job and does not require an API key.

For every scene it extracts:
- narrative intent/theme hints from captions, descriptions and voiceover text;
- scene timing and environment;
- visible character species, keyframe poses and actual positional movement;
- explicit visual state such as a door opening;
- evidence references for each extracted fact.

Crucial separation:
- Narrative text tells the agent what the story is about.
- Structured visual state tells it what is actually visible or happening.
- Narrative mentions like "rain", "footsteps" or "a bird" do not by themselves create SFX.

The audio director consumes this scene report and only schedules effects when there is
matching scene/action evidence. Every render exports `scene-understanding.json` and
`audio-cues.json` beside the MP4 so we can inspect the agent's decisions.

## Multi-agent roadmap

1. Script analyst: segment script, infer scene intent and emotional arc.
2. Scene planner: propose location, shot, props, characters and actions.
3. Character/action planner: output explicit actor manifests and keyframes.
4. Sound director: map evidenced actions and environments to timed audio events.
5. License researcher: source commercial-use recordings and verify each file's license.
6. Continuity/QA agent: catch contradictions, missing visual evidence and timeline errors.
7. Render director: assemble the validated plan.

Groq is a future optional reasoning backend for the analyst/planner. Its output must use
the same structured JSON contract and pass deterministic validation; it cannot directly
force an unsupported sound cue or bypass timeline checks.
