# Stick Animate

A script-driven 2D animation engine with a self-contained native artwork and animation pipeline.

## Run the tests

A push to `main` runs the engine tests only. This deliberately does not call Groq or create a video, because a code push does not contain a story to animate. The Actions summary explains this.

## Render a story on GitHub

1. Open the repository's **Actions** tab.
2. Select **Render Stick Animate demo**.
3. Click **Run workflow** and keep the `main` branch selected.
4. Paste the complete story into **story**. Set the video title and duration.
5. Click **Run workflow** to start production.

The manual run performs these stages:

1. Run the engine tests.
2. Save the submitted story as `input-story.txt`.
3. Make one Groq planning request (when `GROQ_API_KEY` is configured) and save the renderer-ready scene plan.
4. Validate that scene plan.
5. Render the MP4 from that saved plan. Rendering reuses the plan and does not ask Groq to plan the story a second time.
6. Verify the MP4 and audio, then upload the output files as a workflow artifact.

To download the result, open the completed manual workflow run and download its artifact named `stick-animate-scene-designer-N`.

## Runtime requirements

The GitHub runner installs FFmpeg and the Python dependencies. Add `GROQ_API_KEY` as a repository Actions secret to enable Groq planning. The configured model is `openai/gpt-oss-120b`.

The engine is still under active development; a successful render verifies the pipeline and output files, not professional animation quality.

## Native AI-directed artwork

Stick Animate no longer depends on Hugging Face, ComfyUI, or a hosted image-generation endpoint to create story assets. The production planner can describe unknown characters, props, vehicles and backgrounds with a structured `visual_design` brief. The local native artwork compiler turns those briefs into editable SVG, transparent PNG component layers, preview artwork and reusable JSON metadata. Unknown species are assigned an anatomy-aware procedural rig instead of being silently replaced with a human.

The native pipeline is:

1. **AI visual designer:** identifies missing assets and returns their appearance, palette, silhouette, anatomy and component details in the scene plan.
2. **Drawing engine:** compiles those details into local SVG and layered PNG artwork, then caches it in `output/native-assets/`.
3. **Animation engine:** uses native species rigs for motion; unknown species use anatomy archetypes (bird, fish, serpentine, quadruped, biped or multi-limb) while preserving the planned identity.

This is a self-contained vector/procedural illustration system, not a claim of photorealistic or painterly diffusion-model image synthesis. No external image service or stock image is required.

Pull requests render `tests/fixtures/native_artwork_demo.json`, which introduces a penguin and a hover bike, and upload a video proof artifact named `stick-animate-native-artwork-proof`.


## Scene-plan timing

AI scene timestamps are normalized to the requested duration when the model's start/end drift is small (up to 10% or one second). Large timeline mismatches and overlapping scenes remain validation errors.
