# AI asset generation

Stick Animate can discover missing visual assets in a production plan, generate them on demand, cache them, and composite generated artwork into rendered scenes.

## Providers

The renderer does not silently call a paid API. Select and configure a provider explicitly.

### Hugging Face Inference

Set these environment variables in the machine that runs the renderer:

- `STICK_ANIMATE_IMAGE_PROVIDER=huggingface`
- `HF_TOKEN` to a Hugging Face access token
- Optional: `STICK_ANIMATE_IMAGE_MODEL` (default: `black-forest-labs/FLUX.1-schnell`)
- Optional: `STICK_ANIMATE_IMAGE_ENDPOINT` to override the model URL
- Optional: `STICK_ANIMATE_IMAGE_TIMEOUT=240`

Model weights may be openly licensed, but hosted inference is not guaranteed to be free or available on every account. Check the model licence and current provider pricing/quotas before production use.

### ComfyUI

Run a ComfyUI server reachable from the renderer and export an API-format workflow JSON. Configure:

- `STICK_ANIMATE_IMAGE_PROVIDER=comfyui`
- `STICK_ANIMATE_IMAGE_ENDPOINT=http://YOUR-COMFYUI-HOST:8188`
- `STICK_ANIMATE_COMFY_WORKFLOW=/path/to/workflow_api.json`
- `STICK_ANIMATE_COMFY_PROMPT_NODE=6` (positive CLIP text-encode node; default 6)
- `STICK_ANIMATE_COMFY_NEGATIVE_NODE=7` (negative CLIP text-encode node; default 7)
- `STICK_ANIMATE_COMFY_OUTPUT_NODE=9` (reserved for custom workflows; output discovery currently scans workflow outputs)
- Optional: `STICK_ANIMATE_IMAGE_TIMEOUT=240`

The workflow must be in ComfyUI API format and contain the configured prompt nodes with `inputs.text` fields. Keep the server private; do not expose an unauthenticated ComfyUI port to the public internet.

## How the engine requests assets

Groq scene plans can include an `assets` array. Each entry should have `asset_id`, `name`, `kind` (`character`, `prop`, or `background`) and a detailed `prompt`. Scene-specific backgrounds can use `background_prompt` and `background_asset`. The renderer also detects actor species absent from the native rig registry and unsupported prop types.

Generated images are stored under the render output directory in `generated-assets/`, with a `generated-assets.json` manifest. Matching prompt/provider combinations are cached. A scene can use `background_image`; generated unknown-character artwork is composited as a sprite; generated props are composited at their authored normalized coordinates.

## Important current limitation

This is the first asset-generation integration, not a complete character-rig generator. A generated character currently enters the render as a movable image sprite; it does not yet receive articulated limbs, facial animation, lip sync or species-specific gait. The next stage is automatic cutout/segmentation and rig construction, followed by motion validation. If no provider is configured, the renderer reports a warning and preserves its existing native rendering path. Set `STICK_ANIMATE_REQUIRE_AI_ASSETS=1` to fail instead of silently proceeding when a script requests generated assets.
