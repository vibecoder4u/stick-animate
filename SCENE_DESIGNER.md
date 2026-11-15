# Scene Designer

The Scene Designer is a per-video planning stage. It must create a shot list for
each story rather than reuse a single demo storyboard.

## Current baseline

`scene_designer.py` accepts plain story text and a target duration. It:
- splits the story into narrative beats;
- plans one timed shot per beat (merging beats only when duration would make shots too short);
- infers a location from explicit story evidence and carries location continuity when no new place is named;
- chooses a different shot language (establishing wide, medium action, close-up, over-shoulder, low angle, reveal);
- assigns a visual focus, action pose, lighting mood, and camera push/pan;
- emits a renderer-compatible JSON script with `shot_design` metadata.

Example:
```python
from scene_designer import design_story
plan = design_story("The train left the platform. A locked gate opened. He ran into the tunnel.", 30)
```

## Important limitations

This is a deterministic first pass, not a semantic AI director. Location inference uses
story keywords and the renderer still has a limited procedural environment library.
The planner does not yet invent detailed bespoke props, generate image assets, or
guarantee that every noun in an arbitrary script is visually represented. Groq can
later improve semantic planning, but its proposed scene JSON must pass validation and
visual continuity checks before rendering.

## Pipeline contract

Script analyst -> Scene Designer -> character/action planner -> environment/prop builder
-> sound director -> continuity/QA -> renderer.
