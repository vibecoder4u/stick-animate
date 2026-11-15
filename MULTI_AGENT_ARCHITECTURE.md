# Multi-Agent Production Architecture

## Goal
Each video is designed from its own script. The railway demo is a regression fixture,
not a reusable storyboard. No paid model or API key is required to run the fallback.

## Agents
1. **Script Analyst** — extracts ordered beats, characters/species, locations, props,
   actions, emotions and continuity facts.
2. **Scene Designer** — creates a story-specific timed shot list, environments,
   set dressing, composition, lighting and camera language.
3. **Character Director** — specifies character traits, species, expressions, poses
   and normalized animation keyframes.
4. **Motion Director** — specifies camera movement, anticipation, follow-through,
   secondary motion and environmental motion.
5. **Audio Director** — existing evidence-based sound cue planner; narration alone
   never triggers a sound effect.
6. **Continuity/QA** — validates scene timing and renderer-compatible structure
   before the renderer is allowed to run.

## Free-first provider
The runtime uses Python's standard library and the Groq OpenAI-compatible endpoint.
Set `GROQ_API_KEY` as a GitHub Actions repository secret to enable model-driven
creative planning. Optional `GROQ_MODEL` and `LLM_BASE_URL` can override defaults.
Without a key, deterministic planning runs without a network request or paid service.
Groq free-tier availability, rate limits and model access are controlled by Groq and
are not guaranteed by this repository.

## Safety and reliability
- Model output is JSON-only and schema-checked before rendering.
- Scene timing must cover the target runtime without gaps or overlaps.
- Agent failure falls back to deterministic planning.
- The renderer remains separate from creative agents; agents cannot silently patch
  renderer source code at runtime.
- New generated plans are stored in `output/*-scene-plan.json` for inspection.

## Run
```bash
python stick_animate.py --story-file demo/empty_platform_story.txt --duration 30 \
  --title "THE EMPTY PLATFORM" --output output/designed-empty-platform.mp4
```
