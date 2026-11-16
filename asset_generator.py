from __future__ import annotations
"""On-demand AI visual asset generation with optional hosted or local backends.

The planner describes assets; this module owns provider execution, caching and manifests.
No image provider is contacted unless explicitly configured.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from capability_registry import capability_profile


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")[:64] or "asset"


def collect_asset_requests(script: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect explicit planner requests plus unknown actor species and props."""
    requests: dict[str, dict[str, Any]] = {}
    def add(item: Any, scene: dict[str, Any] | None = None) -> None:
        if isinstance(item, str):
            item = {"name": item, "kind": "prop"}
        if not isinstance(item, dict):
            return
        name = str(item.get("name") or item.get("asset_id") or item.get("type") or "").strip()
        if not name:
            return
        kind = str(item.get("kind") or item.get("category") or "prop").lower()
        asset_id = _slug(str(item.get("asset_id") or name))
        entry = {
            "asset_id": asset_id, "name": name, "kind": kind,
            "prompt": str(item.get("prompt") or item.get("visual_description") or
                          f"Original {kind}: {name}. Match the production art direction, clear readable silhouette, polished colorful 2D animation artwork."),
            "negative_prompt": str(item.get("negative_prompt") or
                                   "text, watermark, logo, blurry, low quality, duplicate limbs, cropped subject"),
            "scene_index": item.get("scene_index"),
        }
        if scene is not None and entry["scene_index"] is None:
            entry["scene_index"] = scene.get("_index")
        requests.setdefault(asset_id, entry)

    for item in script.get("asset_requests", []) or []:
        add(item)
    for index, scene in enumerate(script.get("scenes", [])):
        scene["_index"] = index
        for item in scene.get("asset_requests", []) or []:
            add(item, scene)
        if scene.get("background_prompt"):
            add({"asset_id": scene.get("background_asset", f"scene-{index+1}-background"),
                 "name": scene.get("environment", "story location"),
                 "kind": "background", "prompt": scene["background_prompt"]}, scene)
        actors = list(scene.get("actors") or [])
        if scene.get("actor"):
            actors.append(scene["actor"])
        supported = set(capability_profile()["characters"]["native_species"])
        for actor in actors:
            species = str(actor.get("species", "")).lower()
            if species and species not in supported:
                name = str(actor.get("name") or actor.get("character_id") or species)
                add({"asset_id": actor.get("asset_id", f"character-{name}"),
                     "name": name, "kind": "character",
                     "prompt": str(actor.get("visual_description") or
                         f"Original {species} character named {name}; full-body, front three-quarter view, clean separated silhouette, colorful 2D cartoon animation design, consistent proportions, plain transparent-friendly background.")}, scene)
        for prop in scene.get("props", []) or []:
            prop_type = str(prop.get("type") or prop.get("name") or "")
            if prop_type and prop_type not in capability_profile()["props"]:
                add({"asset_id": prop.get("asset_id", f"prop-{prop_type}"),
                     "name": prop_type, "kind": "prop",
                     "prompt": str(prop.get("visual_description") or
                         f"Original story prop: {prop_type}, isolated full object, colorful 2D cartoon animation asset, readable silhouette.")}, scene)
    for scene in script.get("scenes", []):
        scene.pop("_index", None)
    return list(requests.values())


class ImageGenerationUnavailable(RuntimeError):
    pass


class ImageGenerator:
    """Provider adapter supporting Hugging Face Inference and ComfyUI API."""
    def __init__(self) -> None:
        self.provider = os.getenv("STICK_ANIMATE_IMAGE_PROVIDER", "").strip().lower()
        self.model = os.getenv("STICK_ANIMATE_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
        self.endpoint = os.getenv("STICK_ANIMATE_IMAGE_ENDPOINT", "").rstrip("/")
        self.token = os.getenv("HF_TOKEN", "").strip()
        self.workflow_path = os.getenv("STICK_ANIMATE_COMFY_WORKFLOW", "").strip()
        self.output_node = os.getenv("STICK_ANIMATE_COMFY_OUTPUT_NODE", "9")
        self.timeout = max(30, int(os.getenv("STICK_ANIMATE_IMAGE_TIMEOUT", "240")))

    @property
    def available(self) -> bool:
        if self.provider == "huggingface":
            return bool(self.token)
        if self.provider == "comfyui":
            return bool(self.endpoint and self.workflow_path and Path(self.workflow_path).is_file())
        return False

    def generate(self, request: dict[str, Any], destination: Path) -> Path:
        if not self.available:
            raise ImageGenerationUnavailable(
                "No image backend configured. Set STICK_ANIMATE_IMAGE_PROVIDER=huggingface with HF_TOKEN, "
                "or configure STICK_ANIMATE_IMAGE_PROVIDER=comfyui, STICK_ANIMATE_IMAGE_ENDPOINT and "
                "STICK_ANIMATE_COMFY_WORKFLOW."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if self.provider == "huggingface":
            self._huggingface(request, destination)
        elif self.provider == "comfyui":
            self._comfyui(request, destination)
        else:
            raise ImageGenerationUnavailable(f"Unsupported image provider: {self.provider}")
        if not destination.is_file() or destination.stat().st_size < 1024:
            raise ImageGenerationUnavailable("Image provider returned an empty or invalid image")
        return destination

    def _huggingface(self, request: dict[str, Any], destination: Path) -> None:
        url = self.endpoint or f"https://router.huggingface.co/hf-inference/models/{self.model}"
        payload = json.dumps({"inputs": request["prompt"], "parameters": {
            "negative_prompt": request.get("negative_prompt", ""),
        }}).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
            "Accept": "image/png", "User-Agent": "stick-animate-asset-generator/1.0",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = response.read()
                if "image" not in response.headers.get("Content-Type", ""):
                    raise ImageGenerationUnavailable("Hugging Face did not return image data; check model/provider availability")
                destination.write_bytes(data)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ImageGenerationUnavailable(f"Hugging Face image generation failed: {exc}") from exc

    def _comfyui(self, request: dict[str, Any], destination: Path) -> None:
        workflow = json.loads(Path(self.workflow_path).read_text(encoding="utf-8"))
        prompt = request["prompt"]
        positive_node = os.getenv("STICK_ANIMATE_COMFY_PROMPT_NODE", "6")
        negative_node = os.getenv("STICK_ANIMATE_COMFY_NEGATIVE_NODE", "7")
        if positive_node not in workflow or negative_node not in workflow:
            raise ImageGenerationUnavailable("ComfyUI workflow is missing configured positive/negative prompt node IDs")
        workflow[positive_node]["inputs"]["text"] = prompt
        workflow[negative_node]["inputs"]["text"] = request.get("negative_prompt", "")
        body = json.dumps({"prompt": workflow}).encode()
        req = urllib.request.Request(self.endpoint + "/prompt", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                prompt_id = json.loads(response.read())["prompt_id"]
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                with urllib.request.urlopen(self.endpoint + "/history/" + urllib.parse.quote(prompt_id), timeout=20) as response:
                    history = json.loads(response.read())
                record = history.get(prompt_id, {})
                outputs = record.get("outputs", {})
                for node in outputs.values():
                    images = node.get("images", [])
                    if images:
                        image = images[0]
                        query = urllib.parse.urlencode({k: image[k] for k in ("filename", "subfolder", "type") if k in image})
                        with urllib.request.urlopen(self.endpoint + "/view?" + query, timeout=30) as response:
                            destination.write_bytes(response.read())
                        return
                time.sleep(2)
            raise ImageGenerationUnavailable("ComfyUI generation timed out before producing an image")
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            raise ImageGenerationUnavailable(f"ComfyUI image generation failed: {exc}") from exc


def prepare_generated_assets(script: dict[str, Any], output_dir: Path,
                            generator: ImageGenerator | None = None) -> dict[str, str]:
    """Generate/cache requested assets and return asset_id -> absolute image path."""
    generator = generator or ImageGenerator()
    requests = collect_asset_requests(script)
    manifest_path = output_dir / "generated-assets.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
    generated: dict[str, str] = {}
    if requests and not generator.available:
        message = ("AI assets requested but no image backend is configured; using renderer-native assets where available. "
                   "Configure a Hugging Face token or a reachable ComfyUI API to enable generation.")
        print("WARNING: " + message)
        if os.getenv("STICK_ANIMATE_REQUIRE_AI_ASSETS") == "1":
            raise ImageGenerationUnavailable(message)
        return generated
    for item in requests:
        key = hashlib.sha256((item["prompt"] + "|" + generator.provider + "|" + generator.model).encode()).hexdigest()[:16]
        cached = manifest.get(item["asset_id"], {})
        path = Path(cached.get("path", "")) if cached.get("cache_key") == key else Path()
        if path.is_file():
            generated[item["asset_id"]] = str(path.resolve())
            continue
        destination = output_dir / "generated-assets" / f"{item['asset_id']}-{key}.png"
        generator.generate(item, destination)
        manifest[item["asset_id"]] = {"path": str(destination.resolve()), "cache_key": key,
            "kind": item["kind"], "name": item["name"], "prompt": item["prompt"], "provider": generator.provider}
        generated[item["asset_id"]] = str(destination.resolve())
    if generated:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return generated

def attach_generated_assets(script: dict[str, Any], generated: dict[str, str]) -> None:
    """Attach generated image paths to matching scene backgrounds, actors and props."""
    for scene in script.get("scenes", []):
        background_id = scene.get("background_asset")
        if background_id and _slug(str(background_id)) in generated:
            scene["background_image"] = generated[_slug(str(background_id))]
        for actor in list(scene.get("actors") or []) + ([scene["actor"]] if scene.get("actor") else []):
            name = str(actor.get("name") or actor.get("character_id") or actor.get("species") or "character")
            asset_id = _slug(str(actor.get("asset_id") or f"character-{name}"))
            if asset_id in generated:
                actor["_generated_asset_path"] = generated[asset_id]
        for prop in scene.get("props", []) or []:
            name = str(prop.get("type") or prop.get("name") or "prop")
            asset_id = _slug(str(prop.get("asset_id") or f"prop-{name}"))
            if asset_id in generated:
                prop["_generated_asset_path"] = generated[asset_id]
