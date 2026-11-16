# Stick Animate

A script-driven 2D animation engine for story-based faceless videos.

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
