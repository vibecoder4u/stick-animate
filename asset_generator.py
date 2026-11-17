from __future__ import annotations

"""Native asset discovery and compilation.

All requested story assets are drawn inside Stick Animate. There are no hosted
image providers, external image APIs, downloaded stock assets, or cloud image
generation fallbacks in this module.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from capability_registry import capability_profile
from native_artwork import create_native_asset

RENDERER_VERSION = "native-artwork-v1"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:64] or "asset"


def collect_asset_requests(script: dict[str, Any]) -> list[dict[str, Any]]:
    """Find every explicit asset and every character/prop the current rigs lack."""
    requests: dict[str, dict[str, Any]] = {}
    supported_species = set(capability_profile()["characters"]["native_species"])
    supported_props = set(capability_profile()["props"])

    def add(item: Any, scene_index: int | None = None) -> None:
        if isinstance(item, str):
            item = {"name": item, "kind": "prop"}
        if not isinstance(item, dict):
            return
        name = str(item.get("name") or item.get("asset_id") or item.get("type") or "").strip()
        if not name:
            return
        kind = str(item.get("kind") or item.get("category") or "prop").lower()
        asset_id = _slug(str(item.get("asset_id") or name))
        request = {
            "asset_id": asset_id, "name": name, "kind": kind,
            "prompt": str(item.get("prompt") or item.get("visual_description") or item.get("description") or
                          f"Original {kind}: {name}. {item.get('visual_description', '')}"),
            "visual_design": item.get("visual_design") or item.get("design") or {},
            "scene_index": item.get("scene_index", scene_index),
        }
        requests.setdefault(asset_id, request)

    for item in script.get("asset_requests") or script.get("assets") or []:
        add(item)
    for index, scene in enumerate(script.get("scenes", [])):
        for item in scene.get("asset_requests") or []:
            add(item, index)
        if scene.get("background_prompt"):
            add({
                "asset_id": scene.get("background_asset", f"scene-{index+1}-background"),
                "name": scene.get("environment", "story location"), "kind": "background",
                "prompt": scene["background_prompt"],
                "visual_design": scene.get("background_design", {}),
            }, index)
        actors = list(scene.get("actors") or [])
        if scene.get("actor"):
            actors.append(scene["actor"])
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            species = str(actor.get("species") or "").strip().lower().replace("-", "_")
            if species and species not in supported_species:
                name = str(actor.get("name") or actor.get("character_id") or species)
                add({
                    "asset_id": actor.get("asset_id") or f"character-{name}",
                    "name": name, "kind": "character",
                    "prompt": actor.get("visual_description") or
                        f"Original {species} character named {name}. Full-body 2D cartoon character with a clear silhouette, expressive face, consistent colors and separable anatomy.",
                    "visual_design": actor.get("visual_design") or actor.get("design") or {},
                }, index)
        for prop in scene.get("props") or []:
            if not isinstance(prop, dict):
                continue
            prop_type = str(prop.get("type") or prop.get("name") or "").strip()
            if prop_type and prop_type not in supported_props:
                add({
                    "asset_id": prop.get("asset_id") or f"prop-{prop_type}",
                    "name": prop_type, "kind": "prop",
                    "prompt": prop.get("visual_description") or
                        f"Original story object {prop_type}; polished colorful cartoon prop, full object, readable silhouette and clear details.",
                    "visual_design": prop.get("visual_design") or prop.get("design") or {},
                }, index)
    return list(requests.values())


def prepare_generated_assets(script: dict[str, Any], output_dir: Path) -> dict[str, str]:
    """Create/cache native artwork and return asset_id -> preview PNG path."""
    requests = collect_asset_requests(script)
    root = output_dir / "native-assets"
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    except (OSError, ValueError):
        manifest = {}
    generated: dict[str, str] = {}
    for request in requests:
        fingerprint = hashlib.sha256(json.dumps({
            "request": request, "renderer": RENDERER_VERSION,
        }, sort_keys=True, default=str).encode()).hexdigest()
        cached = manifest.get(request["asset_id"], {})
        cached_path = Path(cached.get("path", "")) if cached.get("fingerprint") == fingerprint else None
        if cached_path and cached_path.is_file():
            generated[request["asset_id"]] = str(cached_path.resolve())
            continue
        result = create_native_asset(request, root)
        generated[request["asset_id"]] = result["path"]
        manifest[request["asset_id"]] = {
            "fingerprint": fingerprint, **result,
            "name": request["name"], "kind": request["kind"],
            "renderer": RENDERER_VERSION,
        }
    if requests:
        root.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Native artwork compiler created or reused {len(generated)} story assets.")
    return generated


def attach_generated_assets(script: dict[str, Any], generated: dict[str, str]) -> None:
    """Attach native artwork paths and editable metadata to matching scene manifests."""
    root = None
    for scene in script.get("scenes", []):
        background_id = scene.get("background_asset")
        if background_id:
            asset_id = _slug(str(background_id))
            if asset_id in generated:
                scene["background_image"] = generated[asset_id]
        actors = list(scene.get("actors") or [])
        if scene.get("actor"):
            actors.append(scene["actor"])
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            name = str(actor.get("name") or actor.get("character_id") or actor.get("species") or "character")
            asset_id = _slug(str(actor.get("asset_id") or f"character-{name}"))
            if asset_id in generated:
                actor["_generated_asset_path"] = generated[asset_id]
                actor["_native_asset_path"] = generated[asset_id]
        for prop in scene.get("props") or []:
            if not isinstance(prop, dict):
                continue
            name = str(prop.get("type") or prop.get("name") or "prop")
            asset_id = _slug(str(prop.get("asset_id") or f"prop-{name}"))
            if asset_id in generated:
                prop["_generated_asset_path"] = generated[asset_id]
                prop["_native_asset_path"] = generated[asset_id]
