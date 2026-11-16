from __future__ import annotations
"""Script-driven deterministic storyboard planner with persistent multi-actor casts."""
import re
from typing import Any

ENVIRONMENT_RULES = [
    ("underwater", ("underwater", "under water", "below the surface", "coral reef")),
    ("river", ("river", "riverbank", "stream", "flood", "floodwater", "waterfall")),
    ("jungle", ("jungle", "rainforest", "tropical forest")),
    ("beach", ("beach", "shore", "seaside", "ocean", "sea", "swimming", "swam", "waves")),
    ("platform", ("railway station", "train station", "platform", "last train", "train")),
    ("service_gate", ("service gate", "locked gate", "staff only", "maintenance door")),
    ("tunnel", ("tunnel", "underground", "subway tunnel")),
    ("trackside", ("railway track", "tracks", "trackside", "train tracks")),
    ("exit", ("exit", "exit door", "fire escape", "outside")),
    ("stairwell", ("stairs", "staircase", "stairwell", "steps")),
    ("street", ("street", "road", "alley", "sidewalk", "city")),
    ("rainroom", ("window", "bedroom", "living room", "apartment", "house", "room")),
    ("corridor", ("hallway", "corridor", "passage", "inside")),
    ("forest", ("forest", "woods", "trees")),
    ("ship", ("ship", "boat", "deck", "vessel")),
]
SHOT_TYPES = ("establishing_wide", "medium_action", "close_up", "over_shoulder", "low_angle", "reveal")
SPECIES_WORDS = {
    "elephant": ("elephant", "elephants"), "deer": ("deer", "fawn", "fawns"),
    "fox": ("fox", "foxes"), "rabbit": ("rabbit", "rabbits", "bunny", "bunnies", "hare"),
    "monkey": ("monkey", "monkeys", "ape", "chimpanzee", "gorilla"),
    "turtle": ("turtle", "turtles", "tortoise"), "bear": ("bear", "bears", "grizzly"),
    "dinosaur": ("dinosaur", "t-rex", "trex", "velociraptor"),
    "dog": ("dog", "puppy", "hound", "wolf"), "cat": ("cat", "kitten", "feline"),
    "bird": ("bird", "birds", "eagle", "owl", "crow", "parrot", "sparrow"),
    "fish": ("fish", "shark", "whale", "dolphin"),
}
def _has(text: str, term: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", text.lower()))

def split_beats(story: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", story.strip())
    beats = [p.strip() for p in parts if p.strip()]
    if len(beats) == 1 and len(beats[0]) > 260:
        beats = [p.strip() for p in re.split(r"[,;:]\s+", beats[0]) if p.strip()]
    return beats

def _environment(text: str, previous: str | None) -> str:
    for env, terms in ENVIRONMENT_RULES:
        if any(_has(text, term) for term in terms):
            return env
    return previous or "corridor"

def _focus(text: str) -> str:
    for focus, terms in [
        ("water", ("river", "water", "wave", "flood")), ("animal", ("elephant", "deer", "fox", "rabbit", "bear", "monkey", "turtle")),
        ("tree", ("tree", "branch", "log")), ("shadow", ("shadow", "figure", "silhouette")),
        ("footprints", ("footsteps", "footprints", "ran", "running")),
    ]:
        if any(_has(text, term) for term in terms): return focus
    return "character_action"

def _species_list(text: str) -> list[str]:
    return [species for species, words in SPECIES_WORDS.items() if any(_has(text, word) for word in words)]

def _pose(text: str) -> str:
    t = text.lower()
    rules = [
        ("swim", ("swam", "swimming", "underwater", "dives")), ("fly", ("flew", "flying", "soared", "flapped", "takes flight")),
        ("run", ("ran", "running", "chased", "sprinted", "fled", "escape")),
        ("jump", ("jumped", "jumps", "leapt", "leaped")), ("look_back", ("looked back", "turned", "noticed", "watched")),
        ("listen", ("listened", "heard", "whisper", "sound")), ("stumble", ("fell", "slipped", "stumbled", "tripped")),
        ("push", ("pushed", "push", "moved the tree", "lifted", "together")),
        ("reach", ("picked up", "reached", "handed", "helped", "rescued", "caught", "pulled")),
        ("fear", ("afraid", "terrified", "fear", "horror", "shaking")),
        ("walk", ("walked", "walking", "approached", "entered", "crossed", "climbed")),
    ]
    for pose, terms in rules:
        if any(term in t for term in terms): return pose
    return "idle"

def _cast(story: str) -> list[dict[str, Any]]:
    cast: list[dict[str, Any]] = []
    named = re.compile(r"\b([A-Z][a-z]+)\s+(?:the\s+)?(elephant|deer|fox|rabbit|monkey|turtle|bear|dog|cat|bird|fish|dinosaur)\b")
    covered = set()
    for match in named.finditer(story):
        name, species = match.group(1), match.group(2).lower()
        key = name.lower()
        if key not in covered:
            cast.append({"character_id": key, "name": name, "species": species, "scale": 1.0})
            covered.add(key)
    for species in _species_list(story):
        if not any(a["species"] == species for a in cast):
            cast.append({"character_id": species, "name": species.title(), "species": species, "scale": 1.0})
    if not cast and re.search(r"\b(he|she|him|her|boy|girl|man|woman|person|human)\b", story.lower()):
        cast.append({"character_id":"protagonist","name":"Protagonist","species":"human","scale":1.0})
    return cast

def design_story(story: str, duration: float | None = None, title: str = "Untitled Story", fps: int = 24) -> dict[str, Any]:
    if not story.strip(): raise ValueError("Story text cannot be empty")
    if (duration is not None and duration <= 0) or fps <= 0: raise ValueError("Duration and fps must be positive")
    beats = split_beats(story)
    if not beats: raise ValueError("No story beats found")
    cast = _cast(story)
    weights = []
    for beat in beats:
        lower = beat.lower(); words = len(beat.split())
        action = sum(term in lower for term in ("together","pushed","rescued","fell","storm","blocked","rolled","stuck","caught","crossed"))
        dialogue = 1.35 if '"' in beat or any(term in lower for term in ("said","asked","shouted")) else 1.0
        emotion = 1.3 if any(term in lower for term in ("alone","laughed","scared","thank you","friends","kind","terrified")) else 1.0
        weights.append(max(2.8, 2.2 + words/3.5 + action*1.3) * dialogue * emotion)
    natural_duration = float(duration) if duration is not None else sum(weights)
    durations = [natural_duration/len(beats)]*len(beats) if duration is not None else [natural_duration*w/sum(weights) for w in weights]
    scenes=[]; previous_env=None; previous_active=[]
    for i, beat in enumerate(beats):
        env=_environment(beat, previous_env); previous_env=env; pose=_pose(beat)
        mentioned=_species_list(beat)
        active=[a for a in cast if a["species"] in mentioned]
        # Group language means the complete cast is on screen; otherwise retain actors
        # from the previous beat for pronoun-led continuations.
        group = any(term in beat.lower() for term in ("all animals","everyone","the group","the animals","together","each other","their way"))
        if group: active=list(cast)
        elif not active and any(term in beat.lower() for term in ("they","them","their","he ","she ","it ","the group")):
            active=list(previous_active or cast[:1])
        elif active and any(term in beat.lower() for term in ("helped","rescued","caught","pulled","pushed","together","with")):
            # Include named partners implicated by group/action language.
            active=list(dict.fromkeys(active + previous_active))
        if not active and cast and i == 0: active=list(cast)
        if not active and cast and any(term in beat.lower() for term in ("rain","storm","river","flood","sun","safe","safety")):
            active=list(cast)
        if active: previous_active=active
        shot=SHOT_TYPES[i%len(SHOT_TYPES)]
        zooms={"establishing_wide":(1.0,1.025,-.025),"medium_action":(1.005,1.045,.045),
               "close_up":(1.035,1.09,0.0),"over_shoulder":(1.015,1.055,-.05),
               "low_angle":(1.0,1.04,.065),"reveal":(1.025,1.085,-.07)}
        z0,z1,pan=zooms[shot]; start=round(sum(durations[:i]),3); end=round(sum(durations[:i+1]),3)
        scene={"start":start,"end":end,"environment":env,"description":beat,"caption":beat.upper()[:92],
          "camera":{"shot_type":shot,"zoom_start":z0,"zoom_end":z1,"pan":pan,"track_subject":shot in ("close_up","medium_action","low_angle")},
          "shot_design":{"shot_id":f"shot-{i+1:03d}","shot_type":shot,"location":env,"visual_focus":_focus(beat),
          "primary_action":pose,"lighting_mood":"storm_tension" if any(w in beat.lower() for w in ("rain","storm","flood")) else "story_motivated",
          "continuity_from_previous":"maintain_location" if i and env==scenes[-1]["environment"] else "establish_new_location"}}
        if any(_has(beat,w) for w in ("rain","raining","storm")): scene["weather"]="rain"
        if any(_has(beat,w) for w in ("apple","apples","fruit")): scene["props"]=[{"type":"apples","count":5,"x":.52,"y":.83}]
        if any(term in beat.lower() for term in ("fallen tree","tree blocked","tree blocks","blocked the road","moved the tree","branch")):
            scene.setdefault("props",[]).append({"type":"fallen_tree","x":.52,"y":.79,"length":570})
        actors=[]
        for j, source in enumerate(active):
            actor=dict(source); actor["scale"]=float(source.get("scale",1.0)) * (0.82 if len(active)>5 else 1.0)
            actor["expression"]="fear" if pose in ("fear","look_back","listen","stumble") else "determined" if pose in ("push","reach") else "neutral"
            x=250 + (j%4)*255
            y=590 - (j//4)*95
            actor["keyframes"]=[{"t":0.0,"x":x-18,"y":y,"pose":pose,"facing":1},
                                {"t":1.0,"x":x+18,"y":y,"pose":pose,"facing":1}]
            actors.append(actor)
        if actors:
            scene["actors"]=actors
            scene["actor"]=actors[0]
        scenes.append(scene)
    return {"title":title,"size":[1280,720],"fps":fps,"duration":natural_duration,
      "design_metadata":{"designer":"script-aware-multi-actor-fallback-v2","source":"plain_story_text",
      "scene_count":len(scenes),"cast":[{"character_id":a["character_id"],"name":a["name"],"species":a["species"]} for a in cast],
      "shot_types":[s["shot_design"]["shot_type"] for s in scenes],
      "note":"Script-derived cast and multi-actor shot plan; procedural character assets are rendered separately."},
      "scenes":scenes}
