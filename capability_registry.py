from __future__ import annotations
"""Machine-readable inventory of features the current renderer can actually execute."""
from typing import Any
from character_rigs import available_species
from visual_library import DEFAULT_ASSETS

# These are the only environment families with dedicated animated background plates.
ANIMATED_ENVIRONMENTS = ("beach", "ocean", "sea", "underwater")
PROCEDURAL_ENVIRONMENTS = ("beach", "ocean", "sea", "underwater")
BASE_PLATE_ENVIRONMENTS = ("forest", "jungle", "river", "platform", "service_gate",
                           "tunnel", "trackside", "exit", "stairwell", "street",
                           "rainroom", "corridor", "ship", "desert", "cave",
                           "city", "laboratory", "castle", "mountain", "space")

MOTION_ACTIONS = ("idle", "walk", "run", "jump", "fly", "swim", "push", "reach",
                  "pick_up", "look_back", "listen", "stumble", "fear")
CAMERA_FEATURES = ("zoom", "pan", "subject_tracking", "camera_keyframes", "roll", "shake")
TIMELINE_FEATURES = ("scene_timing", "actor_keyframes", "path_points", "depth_scaling",
                     "body_angle", "head_angle", "gait_phase")
TRANSITIONS = ("fade", "cross_dissolve", "wipe_left", "wipe_right", "wipe_up", "wipe_down")
PROPS = ("fallen_tree", "apple", "apple_cluster")

def capability_profile() -> dict[str, Any]:
    """Return current executable features; do not advertise aspirational capabilities."""
    species = list(available_species())
    return {
        "schema_version": 1,
        "characters": {"native_species": species, "unknown_species_policy":
                       "compile_anatomy_aware_native_rig_from_visual_design; never substitute a human"},
        "native_artwork": {"enabled": True, "formats": ["layered_png", "svg", "metadata_json"],
                           "asset_kinds": ["character", "prop", "background"],
                           "external_image_services_required": False},
        "visual_library": {"enabled": True, "asset_ids": list(DEFAULT_ASSETS),
                           "overlay_types": ["thought_bubble", "sticker", "banner"],
                           "storage": "content_addressed_svg_sha256",
                           "entrance_exit_transitions": ["slide_up", "slide_down", "slide_left", "slide_right", "reveal"]},
        "environments": {
            "animated_backgrounds": list(ANIMATED_ENVIRONMENTS),
            "base_plate_only": list(BASE_PLATE_ENVIRONMENTS),
            "unknown_environment_policy": "base_plate_fallback; do not claim dynamic environmental animation",
        },
        "props": list(PROPS),
        "motion_actions": list(MOTION_ACTIONS),
        "camera": list(CAMERA_FEATURES),
        "timeline": list(TIMELINE_FEATURES),
        "transitions": list(TRANSITIONS),
        "limitations": [
            "Most environment names currently receive only the renderer base plate; only beach/ocean/sea/underwater have dedicated animated environmental layers.",
            "Character rigs are procedural 2D drawings, not full skeletal or 3D rigs.",
            "Unknown species use the native anatomy-aware rig compiler; species-specific bespoke rig refinement remains iterative.",
            "Native artwork is generated as layered vector/raster components; complex painterly image synthesis is not claimed.",
            "The psychology SVG library is a finite starter catalog; unknown concepts require a new native vector symbol to be added or generated."
            "The drawing compiler is local and self-contained; no external image-generation service is required.",
        ],
    }
