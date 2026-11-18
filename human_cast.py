from __future__ import annotations
"""Approved reusable human cast for Stick Animate.

The eight identities share the procedural human rig but have stable visual
profiles. Age variants are visual modifications, not extra permanent cast IDs.
"""
from copy import deepcopy

HUMAN_CAST = {
    "man_1": {"name":"Man 1","gender":"male","age_group":"young_adult","age":25,"scale":1.0,"head_scale":1.0,"accent_rgb":[68,151,190],"wardrobe":"hoodie","hair":"short","hair_rgb":[38,31,29],"skin_rgb":[194,139,103]},
    "man_2": {"name":"Man 2","gender":"male","age_group":"adult","age":38,"scale":1.02,"head_scale":1.0,"accent_rgb":[65,151,112],"wardrobe":"coat","hair":"short","hair_rgb":[48,37,31],"skin_rgb":[190,135,99]},
    "man_3": {"name":"Man 3","gender":"male","age_group":"mature","age":52,"scale":1.04,"head_scale":1.0,"accent_rgb":[177,119,62],"wardrobe":"coat","hair":"side_part","hair_rgb":[76,68,59],"skin_rgb":[183,127,94]},
    "woman_1": {"name":"Woman 1","gender":"female","age_group":"young_adult","age":27,"scale":0.98,"head_scale":1.0,"accent_rgb":[174,91,151],"wardrobe":"hoodie","hair":"long","hair_rgb":[43,29,27],"skin_rgb":[202,151,116]},
    "woman_2": {"name":"Woman 2","gender":"female","age_group":"adult","age":41,"scale":1.0,"head_scale":1.0,"accent_rgb":[111,105,190],"wardrobe":"coat","hair":"long","hair_rgb":[65,48,39],"skin_rgb":[193,141,107]},
    "child_5": {"name":"Child 1","gender":"male","age_group":"child","age":5,"scale":0.76,"head_scale":1.22,"accent_rgb":[231,159,58],"wardrobe":"hoodie","hair":"short","hair_rgb":[47,34,27],"skin_rgb":[201,149,111]},
    "child_9": {"name":"Child 2","gender":"female","age_group":"child","age":9,"scale":0.86,"head_scale":1.14,"accent_rgb":[224,112,126],"wardrobe":"hoodie","hair":"long","hair_rgb":[52,35,31],"skin_rgb":[190,137,104]},
    "child_13": {"name":"Child 3","gender":"male","age_group":"young_teen","age":13,"scale":0.94,"head_scale":1.07,"accent_rgb":[73,165,139],"wardrobe":"hoodie","hair":"short","hair_rgb":[35,31,29],"skin_rgb":[184,130,97]},
}

def character_profile(character_id: str, overrides: dict | None = None) -> dict:
    """Return a copy of an approved character profile with safe scene overrides."""
    key = str(character_id or "man_1").strip().lower()
    if key not in HUMAN_CAST:
        raise ValueError(f"Unapproved human character_id: {key}")
    profile = deepcopy(HUMAN_CAST[key])
    profile["character_id"] = key
    if overrides:
        for field in ("scale","head_scale","accent_rgb","wardrobe","hair","hair_rgb","skin_rgb","expression","age_variant","accessories"):
            if field in overrides:
                profile[field] = overrides[field]
    return profile

def apply_age_variant(actor: dict, variant: str) -> dict:
    """Apply elderly/child appearance while retaining the approved base identity."""
    result = dict(actor)
    variant = str(variant or "adult").lower()
    if variant in {"elderly","old","senior"}:
        result.update({"age_variant":"elderly","hair":"white","hair_rgb":[220,222,218],
                       "scale":float(result.get("scale",1.0))*0.98,
                       "posture":"slightly_bent","accessories":["walking_stick","wrinkles"]})
    elif variant in {"child_5","child_9","child_13"}:
        result.update(character_profile(variant))
    return result
