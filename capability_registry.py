from __future__ import annotations
"""Machine-readable inventory of features the current renderer can actually execute."""
from typing import Any
from character_rigs import available_species
from human_cast import HUMAN_CAST
from sticker_library import sticker_catalog

ANIMATED_ENVIRONMENTS = ("beach", "ocean", "sea", "underwater")
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
    return {
        "schema_version": 2,
        "characters": {"native_species": list(available_species()),
                       "approved_human_cast": {key: {"name": value["name"], "age": value["age"], "gender": value["gender"]} for key, value in HUMAN_CAST.items()},
                       "special_character_policy": "manual_user_approval_and_asset_creation_required",
                       "unknown_species_policy": "do_not_silently_substitute; require manual approval"},
        "environments": {"animated_backgrounds": list(ANIMATED_ENVIRONMENTS),
                         "base_plate_only": list(BASE_PLATE_ENVIRONMENTS),
                         "unknown_environment_policy": "base_plate_fallback; do not claim dynamic environmental animation"},
        "stickers": sticker_catalog(),
        "props": list(PROPS), "motion_actions": list(MOTION_ACTIONS),
        "camera": list(CAMERA_FEATURES), "timeline": list(TIMELINE_FEATURES),
        "transitions": list(TRANSITIONS),
        "limitations": [
            "Only beach/ocean/sea/underwater have dedicated animated environmental layers.",
            "Character rigs are procedural 2D drawings, not full skeletal or 3D rigs.",
            "Only the eight approved human identities are in the default cast; animals and other special characters require user approval and asset creation.",
            "The language model plans scenes; it does not itself generate raster artwork or new character rigs.",
        ],
    }
