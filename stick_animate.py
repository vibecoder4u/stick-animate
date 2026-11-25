from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from audio_director import render_audio
from sound_effect_finder import find_and_mix_effects
from scene_understanding_agent import analyse_script
from scene_designer import design_story
from production_agents import design_production
from character_rigs import draw_species_character
from human_cast import HUMAN_CAST, character_profile, apply_age_variant
from sticker_library import draw_stickers
from camera_director import apply_camera
from environment_animation import render_environment_background, animate_environment
from transition_engine import crossfade, transition_duration
from motion_composer import motion_for_actor


W, H = 1280, 720
FPS = 24
COLORS = {
    "ink": (8, 12, 20), "wall": (21, 29, 43), "floor": (13, 19, 29),
    "light": (235, 241, 250), "muted": (151, 167, 188),
    "cyan": (111, 207, 225), "red": (190, 65, 67),
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def validate_script(data: dict[str, Any]) -> None:
    required = ("title", "duration", "fps", "scenes")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError("Missing script fields: " + ", ".join(missing))
    if not isinstance(data["scenes"], list) or not data["scenes"]:
        raise ValueError("Script needs at least one scene")
    if float(data["duration"]) <= 0 or int(data["fps"]) <= 0:
        raise ValueError("Duration and fps must be positive")
    previous_end = 0.0
    for index, scene in enumerate(data["scenes"]):
        start, end = float(scene["start"]), float(scene["end"])
        if start < 0 or end <= start or end > float(data["duration"]) + 0.001:
            raise ValueError(f"Invalid scene timing at scene {index}")
        if start < previous_end - 0.001:
            raise ValueError("Scenes must be ordered and cannot overlap")
        if start > previous_end + 0.001:
            raise ValueError(f"Timeline gap before scene {index}: {previous_end:.3f}s to {start:.3f}s")
        previous_end = end
        cast = list(scene.get("actors") or [])
        if scene.get("actor"):
            cast.insert(0, scene["actor"])
        for actor_index, actor in enumerate(cast):
            keys = actor.get("keyframes", [])
            if keys:
                times = [float(k["t"]) for k in keys]
                if times != sorted(times) or times[0] < 0 or times[-1] > 1:
                    raise ValueError(f"Invalid keyframes for actor {actor_index} in scene {index}")
    if previous_end < float(data["duration"]) - 0.001:
        raise ValueError(f"Timeline ends at {previous_end:.3f}s before declared duration {float(data['duration']):.3f}s")


def sample_keyframes(keyframes: list[dict[str, Any]], progress: float) -> dict[str, Any]:
    if not keyframes:
        return {"x": 640.0, "y": 610.0, "pose": "idle", "facing": 1}
    p = min(1.0, max(0.0, progress))
    if p <= float(keyframes[0]["t"]):
        return dict(keyframes[0])
    if p >= float(keyframes[-1]["t"]):
        return dict(keyframes[-1])
    for left, right in zip(keyframes, keyframes[1:]):
        a, b = float(left["t"]), float(right["t"])
        if a <= p <= b:
            span = max(0.000001, b - a)
            u = (p - a) / span
            u = u * u * (3.0 - 2.0 * u)  # smoothstep
            result = dict(left)
            # Interpolate every authored numeric control (position, rotation,
            # action progress, body lean, etc.); keep categorical controls discrete.
            for key in set(left) & set(right):
                if key == "t" or key in {"pose", "facing"}:
                    continue
                lv, rv = left[key], right[key]
                if isinstance(lv, (int, float)) and not isinstance(lv, bool) and isinstance(rv, (int, float)) and not isinstance(rv, bool):
                    result[key] = float(lv) + (float(rv) - float(lv)) * u
            if u >= 0.5:
                result["pose"] = right.get("pose", result.get("pose", "idle"))
                result["facing"] = right.get("facing", result.get("facing", 1))
            return result
    return dict(keyframes[-1])


def gradient_background(kind: str) -> Image.Image:
    palettes = {
        "corridor": ((18, 27, 42), (5, 8, 15)),
        "stairwell": ((24, 34, 48), (6, 10, 18)),
        "rainroom": ((20, 34, 48), (5, 10, 18)),
        "street": ((26, 34, 47), (5, 8, 14)),
        "forest": ((91, 157, 181), (24, 65, 48)),
        "laboratory": ((37, 61, 83), (8, 18, 31)),
        "road": ((113, 160, 178), (43, 75, 59)),
    }
    palettes.update({
        "platform": ((25, 39, 55), (4, 9, 16)),
        "service_gate": ((22, 34, 48), (4, 8, 15)),
        "tunnel": ((13, 23, 35), (1, 4, 9)),
        "exit": ((30, 38, 48), (5, 8, 14)),
        "trackside": ((17, 30, 43), (2, 6, 12)),
    })
    top, bottom = palettes.get(kind, palettes["corridor"])
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    for y in range(H):
        p = y / (H - 1)
        color = tuple(int(top[i] * (1 - p) + bottom[i] * p) for i in range(3))
        draw.line((0, y, W, y), fill=color)
    if kind in ("forest", "road"):
        # Layered forest silhouette with a readable path, trunks, canopy and foreground.
        draw.polygon([(0, 390), (180, 275), (360, 380), (560, 245), (760, 370),
                      (980, 250), (1280, 390), (1280, 560), (0, 560)], fill=(42, 105, 78))
        draw.polygon([(0, 465), (220, 365), (430, 470), (700, 340), (960, 455),
                      (1120, 355), (1280, 440), (1280, 610), (0, 610)], fill=(28, 82, 58))
        # Open walking path recedes into the forest.
        draw.polygon([(520, 430), (760, 430), (1030, 720), (240, 720)], fill=(126, 105, 76))
        for tx, top, width in ((85,150,52),(245,190,44),(1010,155,58),(1190,205,42)):
            draw.rectangle((tx-width//4, top+125, tx+width//4, 590), fill=(83, 57, 39))
            draw.ellipse((tx-width, top, tx+width, top+150), fill=(36, 105, 66))
            draw.ellipse((tx-width+25, top+35, tx+width+25, top+170), fill=(47, 124, 75))
        for gx in range(0, W, 38):
            draw.line((gx, 640, gx-12, 610), fill=(66, 126, 67), width=3)
        return image
    if kind == "trackside":
        # Low track-level chase shot: rails, sleepers, train flank and signal.
        draw.rectangle((0, 100, W, 460), fill=(9, 18, 29))
        draw.polygon([(0, 300), (W, 300), (W, 720), (0, 720)], fill=(5, 9, 15))
        draw.polygon([(0, 170), (W, 170), (1050, 410), (220, 410)], fill=(23, 37, 50))
        draw.rectangle((40, 185, 330, 430), fill=(20, 34, 47), outline=(105, 124, 139), width=5)
        for x in (75, 145, 215, 285):
            draw.rectangle((x, 220, x+48, 315), fill=(63, 99, 120), outline=(139, 157, 166), width=2)
        draw.line((360, 390, 120, 720), fill=(139, 153, 160), width=8)
        draw.line((910, 390, 1160, 720), fill=(139, 153, 160), width=8)
        for i in range(11):
            y = 420 + i*28
            half = 260 + i*22
            draw.line((640-half, y, 640+half, y), fill=(62, 74, 83), width=7)
        draw.line((1060, 100, 1060, 430), fill=(105, 120, 133), width=8)
        draw.ellipse((1037, 145, 1083, 191), fill=(197, 49, 46))
        draw.ellipse((1044, 202, 1076, 234), fill=(55, 74, 84))
        return image
    if kind == "platform":
        # A recognisable underground railway platform: canopy, columns, tracks,
        # platform edge, station signage, bench and a stopped train in the distance.
        draw.rectangle((0, 92, W, 390), fill=(15, 26, 39))
        draw.polygon([(0, 92), (W, 92), (1110, 205), (170, 205)], fill=(31, 45, 59))
        for x in (110, 390, 670, 950, 1190):
            draw.polygon([(x-18, 175), (x+18, 175), (x+31, 520), (x-31, 520)], fill=(49, 63, 76))
            draw.rectangle((x-24, 180, x+24, 196), fill=(112, 130, 145))
        for x in (170, 450, 730, 1010):
            draw.polygon([(x-58, 108), (x+58, 108), (x+36, 120), (x-36, 120)], fill=(194, 205, 207))
            draw.line((x-42, 114, x+42, 114), fill=(239, 226, 185), width=3)
        # Tracks recede to a vanishing point; sleepers and rails make the location legible.
        draw.polygon([(0, 548), (W, 548), (W, H), (0, H)], fill=(5, 9, 15))
        for x0, x1 in ((430, 80), (850, 1200)):
            draw.line((x0, 545, x1, 720), fill=(119, 135, 148), width=7)
        for i in range(10):
            y = 565 + i*18
            half = 30 + i*24
            draw.line((640-half, y, 640+half, y), fill=(64, 76, 86), width=5)
        draw.line((0, 525, W, 525), fill=(222, 185, 92), width=7)
        draw.line((0, 535, W, 535), fill=(100, 112, 119), width=2)
        # Distant train car, windows and station sign.
        draw.rectangle((465, 260, 815, 410), fill=(28, 44, 58), outline=(118, 137, 149), width=5)
        for x in (490, 555, 620, 685, 750):
            draw.rectangle((x, 280, x+48, 335), fill=(82, 119, 139), outline=(160, 174, 181), width=2)
        draw.rectangle((70, 220, 350, 280), fill=(7, 17, 27), outline=(124, 148, 159), width=3)
        draw.text((91, 233), "PLATFORM  02", font=font(27, True), fill=(225, 230, 222))
        draw.rectangle((80, 430, 250, 495), fill=(37, 48, 57), outline=(112, 126, 136), width=3)
        draw.line((90, 430, 90, 500), fill=(112, 126, 136), width=5)
        return image
    # Dedicated warm story locations (illustrated reusable plates, no generic corridor fallback).
    if kind in ("bedroom", "home", "living_room", "house"):
        draw.rectangle((0,105,W,525),fill=(220,203,177)); draw.rectangle((0,525,W,H),fill=(142,104,76))
        draw.rectangle((75,165,430,420),fill=(117,169,205),outline=(245,234,212),width=18)
        draw.line((250,165,250,420),fill=(245,234,212),width=12); draw.line((75,290,430,290),fill=(245,234,212),width=12)
        draw.rectangle((790,360,1180,525),fill=(94,66,52)); draw.rectangle((820,330,1150,385),fill=(184,139,105))
        draw.rectangle((900,250,1080,335),fill=(240,216,177)); draw.ellipse((935,265,1045,315),fill=(190,140,104))
        draw.rectangle((0,510,W,530),fill=(91,68,53)); return image
    if kind in ("classroom", "school"):
        draw.rectangle((0,105,W,525),fill=(224,213,187)); draw.rectangle((0,525,W,H),fill=(138,102,72))
        draw.rectangle((180,150,1100,385),fill=(42,93,77),outline=(192,177,142),width=16)
        draw.text((450,220),"LEARN  •  GROW",font=font(40,True),fill=(234,235,211))
        for x in (110,440,770):
            draw.rectangle((x,420,x+250,490),fill=(166,111,68));draw.rectangle((x+20,490,x+40,565),fill=(90,66,48));draw.rectangle((x+210,490,x+230,565),fill=(90,66,48))
        return image
    if kind in ("office", "workplace"):
        draw.rectangle((0,105,W,525),fill=(194,205,210));draw.rectangle((0,525,W,H),fill=(114,105,92))
        for x in (90,470,850):
            draw.rectangle((x,150,x+280,390),fill=(91,144,176),outline=(232,237,238),width=14)
            draw.line((x+140,150,x+140,390),fill=(232,237,238),width=8)
        draw.rectangle((300,440,980,500),fill=(127,91,66));draw.rectangle((360,500,390,590),fill=(78,59,48));draw.rectangle((900,500,930,590),fill=(78,59,48))
        return image
    if kind in ("park", "garden"):
        draw.rectangle((0,105,W,525),fill=(151,205,230));draw.ellipse((940,80,1080,220),fill=(255,227,155))
        draw.rectangle((0,430,W,H),fill=(83,156,88));draw.polygon([(500,430),(770,430),(1100,720),(180,720)],fill=(183,166,126))
        for x in (100,300,1000,1180):
            draw.rectangle((x-18,280,x+18,570),fill=(115,78,48));draw.ellipse((x-100,160,x+100,340),fill=(56,139,69));draw.ellipse((x-70,210,x+120,370),fill=(74,159,82))
        return image
    # Architectural planes and a deliberately simple vanishing-point composition.
    draw.polygon([(0, 105), (W, 105), (W, 525), (0, 525)], fill=(17, 25, 38))
    draw.polygon([(0, 525), (W, 525), (W, H), (0, H)], fill=(8, 13, 22))
    draw.line((0, 525, W, 525), fill=(53, 67, 83), width=3)
    vp = (640, 260)
    for x in range(-500, 1801, 210):
        draw.line((vp[0], vp[1], x, H), fill=(28, 39, 53), width=2)
    for y in (565, 610, 675):
        draw.line((0, y, W, y), fill=(21, 31, 44), width=2)
    # Repeating ceiling lights and wall seams.
    for x in (165, 445, 725, 1005):
        draw.polygon([(x - 58, 112), (x + 58, 112), (x + 34, 123), (x - 34, 123)], fill=(73, 91, 111))
        draw.line((x - 40, 117, x + 40, 117), fill=(154, 170, 185), width=2)
    for x in (85, 335, 585, 835, 1085, 1250):
        draw.line((x, 125, x, 520), fill=(25, 36, 50), width=2)
    if kind == "service_gate":
        draw.rectangle((760, 145, 1175, 525), fill=(5, 10, 17), outline=(105, 122, 137), width=12)
        for x in range(785, 1160, 30):
            draw.line((x, 160, x, 520), fill=(104, 121, 136), width=7)
        draw.rectangle((780, 160, 1155, 182), fill=(143, 158, 166))
        draw.rectangle((790, 480, 1145, 510), fill=(36, 49, 61))
        draw.text((835, 205), "STAFF ONLY", font=font(22, True), fill=(190, 199, 200))
    elif kind == "tunnel":
        draw.polygon([(0, 150), (W, 150), (1010, 540), (270, 540)], fill=(3, 8, 14))
        draw.arc((250, 120, 1030, 700), 180, 360, fill=(83, 101, 115), width=15)
        for x in (430, 850):
            draw.ellipse((x-15, 280, x+15, 310), fill=(224, 185, 105))
        draw.line((390, 545, 560, 720), fill=(104, 119, 130), width=5)
        draw.line((890, 545, 720, 720), fill=(104, 119, 130), width=5)
    elif kind == "exit":
        draw.rectangle((850, 125, 1160, 525), fill=(3, 7, 13), outline=(112, 126, 138), width=12)
        draw.rectangle((870, 145, 1140, 505), fill=(18, 32, 43))
        draw.polygon([(880, 500), (1130, 500), (1230, 720), (760, 720)], fill=(137, 158, 169, 38))
        draw.rectangle((885, 155, 1125, 188), fill=(135, 151, 160))
    elif kind == "rainroom":
        draw.rectangle((920, 150, 1190, 510), fill=(7, 15, 27), outline=(87, 113, 133), width=8)
        draw.line((1055, 155, 1055, 505), fill=(69, 91, 111), width=4)
        draw.line((925, 330, 1185, 330), fill=(69, 91, 111), width=4)
    elif kind == "stairwell":
        draw.polygon([(820, 525), (1170, 245), (1170, 525)], fill=(10, 16, 26))
        for i in range(7):
            y = 280 + i * 34
            x = 850 + i * 42
            draw.line((x, y, 1170, y), fill=(50, 63, 80), width=5)
    elif kind == "street":
        draw.rectangle((70, 160, 300, 500), fill=(10, 17, 28), outline=(40, 56, 73), width=5)
        draw.rectangle((340, 195, 570, 500), fill=(9, 15, 25), outline=(40, 56, 73), width=5)
        draw.rectangle((980, 115, 1210, 500), fill=(9, 15, 25), outline=(40, 56, 73), width=5)
    return image


def draw_door(draw: ImageDraw.ImageDraw, opening: float = 0.0, glow: float = 0.0) -> None:
    x0, y0, x1, y1 = 890, 188, 1090, 526
    draw.rectangle((x0 - 13, y0 - 13, x1 + 13, y1 + 8), fill=(5, 9, 16), outline=(82, 98, 116), width=7)
    # Door leaf pivots from its right edge; opening reveals a narrow strip of light.
    reveal = int(154 * min(1.0, max(0.0, opening)))
    draw.rectangle((x0 + 8, y0 + 8, x1 - 8, y1), fill=(4, 7, 12))
    if reveal:
        draw.rectangle((x1 - reveal, y0 + 8, x1 - 7, y1 - 2), fill=(154, 178, 194))
        draw.rectangle((x1 - reveal + 3, y0 + 12, x1 - 10, y1 - 8), fill=(218, 229, 237))
    if glow > 0:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        alpha = int(95 * min(1, glow))
        ld.polygon([(x1 - 175, y0 + 8), (x1 + 20, y0 + 8), (x1 + 220, H), (x1 - 310, H)], fill=(129, 190, 215, alpha))
        overlay = Image.alpha_composite(Image.new("RGBA", (W, H)), layer)
        # Caller composites separately; drawing a subtle source glow is enough here.
        draw.rectangle((x1 - 9, y0 + 5, x1 + 1, y1), fill=(180, 211, 225))


def draw_character(image: Image.Image, x: float, foot_y: float, pose: str, facing: int, t: float, scale: float = 1.0, actor: dict[str, Any] | None = None) -> None:
    d = ImageDraw.Draw(image)
    motion = actor.get("_motion", {}) if actor else {}
    phase = float(motion.get("phase", t * (11.5 if pose == "run" else 7.0)))
    stride = math.sin(phase)
    f = 1 if facing >= 0 else -1
    s = scale
    lean = float(motion.get("torso_lean", 0.0))
    bob = float(motion.get("body_bob", 0.0))
    head_bob = float(motion.get("head_bob", 0.0))
    arm_swing = float(motion.get("arm_swing", 0.0))
    def pt(px: float, py: float) -> tuple[int, int]:
        height_weight = max(0.0, min(1.0, -py / 145.0))
        return (int(x + (px + lean * height_weight) * s * f),
                int(foot_y + (py * s) + bob * height_weight + head_bob * height_weight))
    actor = actor or {}
    color = tuple(actor.get("accent_rgb", [87, 151, 177]))
    pants = tuple(actor.get("pants_rgb", [40, 49, 63]))
    skin = tuple(actor.get("skin_rgb", [222, 177, 145]))
    head_scale = max(0.85, min(1.35, float(actor.get("head_scale", 1.0))))
    shadow = (3, 6, 11)
    ground_y = float(actor.get("_ground_y", foot_y))
    d.ellipse((x - 32*s, ground_y - 11*s, x + 32*s, ground_y + 5*s), fill=(2, 5, 9))
    # Local skeleton, with small procedural motion layered over authored poses.
    head_y = -145
    shoulder_y = -104
    hip_y = -52
    if pose == "crouch":
        head_y, shoulder_y, hip_y = -112, -79, -38
    elif pose in ("look_back", "listen"):
        head_y, shoulder_y, hip_y = -150, -105, -52
    elif pose == "stumble":
        head_y, shoulder_y, hip_y = -125, -92, -44
    # torso and neck
    wardrobe = str(actor.get("wardrobe", "hoodie")).lower()
    torso_fill = (35, 48, 63) if wardrobe == "coat" else color
    torso_outline = tuple(max(0, int(channel * 0.72)) for channel in color)
    d.polygon([pt(-21, shoulder_y), pt(21, shoulder_y), pt(17, hip_y + 5), pt(-17, hip_y + 5)],
              fill=torso_fill, outline=torso_outline)
    d.line((pt(0, head_y + 31), pt(0, shoulder_y)), fill=skin, width=max(6, int(10*s)))
    d.line((pt(0, shoulder_y), pt(0, hip_y)), fill=color, width=max(7, int(14*s)))
    # Head: clean readable silhouette with two tiny facial marks.
    hx, hy = pt(0, head_y)
    r = 29*s*head_scale
    d.ellipse((hx-r, hy-r, hx+r, hy+r), fill=skin, outline=(73,54,45), width=max(1,int(2*s)))
    eye_x = hx + f * 10*s
    eye_y = hy - 5*s
    d.ellipse((eye_x-3*s, eye_y-4*s, eye_x+3*s, eye_y+3*s), fill=(26, 36, 48))
    # Character-specific silhouette details (hair, expression, shirt and footwear).
    hair = str(actor.get("hair", "short")).lower()
    hair_color = tuple(actor.get("hair_rgb", [42, 32, 28]))
    if hair in ("short", "side_part"):
        d.arc((hx-r*1.02,hy-r*1.08,hx+r*1.02,hy+r*.35),180,355,fill=hair_color,width=max(5,int(10*s)))
        d.polygon([pt(-r*.72,head_y-r*.42),pt(-r*.38,head_y-r*1.02),pt(r*.2,head_y-r*1.04),pt(r*.88,head_y-r*.42)],fill=hair_color)
        if hair=="side_part": d.line((pt(0,head_y-r*.92),pt(-r*.25,head_y-r*.42)),fill=(100,78,63),width=max(1,int(2*s)))
    elif hair in ("long","curly"):
        d.polygon([pt(-r*.9,head_y-r*.65),pt(-r*1.1,head_y+r*.8),pt(-r*.65,head_y+r*1.35),pt(-r*.35,head_y+r*.35)],fill=hair_color)
        d.polygon([pt(r*.9,head_y-r*.65),pt(r*1.1,head_y+r*.8),pt(r*.65,head_y+r*1.35),pt(r*.35,head_y+r*.35)],fill=hair_color)
        d.arc((hx-r,hy-r*1.1,hx+r,hy+r*.25),180,355,fill=hair_color,width=max(5,int(9*s)))
    expression=str(actor.get("expression","neutral")).lower()
    brow_y=hy-12*s
    brow_color=(55,40,34)
    if expression in ("angry","determined"):
        d.line((eye_x-9*s,brow_y+3*s,eye_x+2*s,brow_y-2*s),fill=brow_color,width=max(2,int(3*s)))
    elif expression in ("sad","worried","fear","scared"):
        d.line((eye_x-8*s,brow_y-2*s,eye_x+2*s,brow_y+3*s),fill=brow_color,width=max(2,int(3*s)))
    else:
        d.line((eye_x-7*s,brow_y,eye_x+2*s,brow_y),fill=brow_color,width=max(2,int(3*s)))
    mouth_y=hy+12*s
    if expression in ("happy","joy","smile"):
        d.arc((hx-9*s,mouth_y-4*s,hx+9*s,mouth_y+12*s),0,180,fill=(102,49,44),width=max(2,int(3*s)))
    elif expression in ("surprised","shock"):
        d.ellipse((hx-3*s, mouth_y,hx+4*s,mouth_y+8*s),outline=(102,49,44),width=max(2,int(3*s)))
    elif expression in ("sad","worried","fear","scared"):
        d.arc((hx-8*s,mouth_y+4*s,hx+8*s,mouth_y+13*s),180,350,fill=(102,49,44),width=max(2,int(3*s)))
    else:
        d.line((hx-6*s,mouth_y+4*s,hx+6*s,mouth_y+4*s),fill=(102,49,44),width=max(2,int(2*s)))
    # Neck/shoulder joints
    d.ellipse((pt(-24, shoulder_y-5)[0]-5*s, pt(-24, shoulder_y-5)[1]-5*s,
               pt(-24, shoulder_y-5)[0]+5*s, pt(-24, shoulder_y-5)[1]+5*s), fill=color)
    d.ellipse((pt(24, shoulder_y-5)[0]-5*s, pt(24, shoulder_y-5)[1]-5*s,
               pt(24, shoulder_y-5)[0]+5*s, pt(24, shoulder_y-5)[1]+5*s), fill=color)

    if pose in ("walk", "run"):
        amp = 33 if pose == "run" else 23
        lift = 17 if pose == "run" else 8
        for side in (-1, 1):
            swing = stride * amp * side
            knee = (side * 12 + swing * 0.52, -26 - abs(stride) * 4)
            ankle = (side * 13 + swing, -max(0, lift * max(0, stride * side)))
            d.line((pt(side*10, hip_y), pt(*knee), pt(*ankle)), fill=pants, width=max(9, int(14*s)), joint="curve")
        arm_amp = 24 if pose == "run" else 16
        for side in (-1, 1):
            elbow = (side * 39 - stride * arm_amp * side, -70)
            hand = (side * 47 - stride * arm_amp * 1.5 * side, -43)
            d.line((pt(side*22, shoulder_y), pt(*elbow), pt(*hand)), fill=color, width=max(8, int(13*s)), joint="curve")
    elif pose == "reach":
        d.line((pt(-22, shoulder_y), pt(-42, -72), pt(-48, -35)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(22, shoulder_y), pt(53, -112), pt(95, -133)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(-10, hip_y), pt(-17, -22), pt(-18, 0)), fill=pants, width=max(9, int(14*s)))
        d.line((pt(10, hip_y), pt(18, -22), pt(21, 0)), fill=pants, width=max(9, int(14*s)))
    elif pose == "jump":
        # Airborne silhouette: arms lift, knees tuck and the body follows a smooth arc.
        for side in (-1, 1):
            d.line((pt(side*22, shoulder_y), pt(side*39, -137), pt(side*48, -166)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(side*10, hip_y), pt(side*29, -28), pt(side*34, -8)), fill=pants, width=max(9, int(14*s)), joint="curve")
    elif pose == "push":
        # Both arms extend in the facing direction so the action reads as contact.
        d.line((pt(-22, shoulder_y), pt(-42, -76), pt(-55, -48)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(22, shoulder_y), pt(48, -116), pt(82, -112)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(-10, hip_y), pt(-17, -22), pt(-18, 0)), fill=pants, width=max(9, int(14*s)))
        d.line((pt(10, hip_y), pt(24, -18), pt(30, 0)), fill=pants, width=max(9, int(14*s)))
    elif pose == "look_back":
        d.line((pt(-22, shoulder_y), pt(-48, -78), pt(-58, -55)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(22, shoulder_y), pt(43, -122), pt(58, -145)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(-10, hip_y), pt(-18, -24), pt(-20, 0)), fill=pants, width=max(9, int(14*s)))
        d.line((pt(10, hip_y), pt(18, -24), pt(20, 0)), fill=pants, width=max(9, int(14*s)))
    elif pose == "listen":
        d.line((pt(-22, shoulder_y), pt(-43, -80), pt(-38, -45)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(22, shoulder_y), pt(37, -88), pt(29, -52)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(-10, hip_y), pt(-18, -24), pt(-18, 0)), fill=pants, width=max(9, int(14*s)))
        d.line((pt(10, hip_y), pt(18, -24), pt(18, 0)), fill=pants, width=max(9, int(14*s)))
    elif pose == "stumble":
        d.line((pt(-22, shoulder_y), pt(-50, -132), pt(-75, -122)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(22, shoulder_y), pt(45, -68), pt(65, -48)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(-10, hip_y), pt(-42, -20), pt(-57, 0)), fill=pants, width=max(9, int(14*s)))
        d.line((pt(10, hip_y), pt(28, -16), pt(45, 0)), fill=pants, width=max(9, int(14*s)))
    elif pose == "fear":
        for side in (-1, 1):
            d.line((pt(side*22, shoulder_y), pt(side*45, -135), pt(side*30, -176)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(side*10, hip_y), pt(side*16, -24), pt(side*18, 0)), fill=pants, width=max(9, int(14*s)))
    elif pose == "crouch":
        for side in (-1, 1):
            d.line((pt(side*20, shoulder_y), pt(side*43, -52), pt(side*54, -78)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(side*10, hip_y), pt(side*35, -8), pt(side*24, 0)), fill=pants, width=max(9, int(14*s)))
    elif pose in ("wave", "point", "talk", "think", "celebrate", "comfort", "hand_over", "pick_up", "open", "climb", "fall", "sit", "kneel", "turn"):
        # Procedural gesture family: shared joint landmarks, distinct silhouettes.
        gesture = float(motion.get("gesture", 0.5))
        if pose == "wave":
            d.line((pt(-22, shoulder_y), pt(-40, -75), pt(-44, -42)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(22, shoulder_y), pt(43, -132-8*gesture), pt(62, -164-10*gesture)), fill=color, width=max(8, int(13*s)), joint="curve")
        elif pose == "point":
            d.line((pt(-22, shoulder_y), pt(-40, -75), pt(-44, -42)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(22, shoulder_y), pt(48, -105), pt(94, -112)), fill=color, width=max(8, int(13*s)), joint="curve")
        elif pose in ("talk", "comfort", "hand_over", "open"):
            d.line((pt(-22, shoulder_y), pt(-43, -78), pt(-35, -47)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(22, shoulder_y), pt(45, -92), pt(65 if pose != "hand_over" else 83, -70)), fill=color, width=max(8, int(13*s)), joint="curve")
        elif pose == "think":
            d.line((pt(-22, shoulder_y), pt(-42, -76), pt(-34, -46)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(22, shoulder_y), pt(38, -118), pt(23, -143)), fill=color, width=max(8, int(13*s)), joint="curve")
        elif pose == "celebrate":
            for side in (-1, 1):
                d.line((pt(side*22, shoulder_y), pt(side*42, -137), pt(side*48, -169)), fill=color, width=max(8, int(13*s)), joint="curve")
        elif pose in ("pick_up", "fall", "sit", "kneel", "climb"):
            d.line((pt(-22, shoulder_y), pt(-43, -76), pt(-55, -35 if pose == "pick_up" else -48)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(22, shoulder_y), pt(44, -76), pt(57, -40)), fill=color, width=max(8, int(13*s)), joint="curve")
        else:
            d.line((pt(-22, shoulder_y), pt(-40, -75), pt(-44, -42)), fill=color, width=max(8, int(13*s)), joint="curve")
            d.line((pt(22, shoulder_y), pt(40, -75), pt(44, -42)), fill=color, width=max(8, int(13*s)), joint="curve")
        if pose in ("sit", "kneel"):
            for side in (-1, 1):
                d.line((pt(side*10, hip_y), pt(side*30, -22), pt(side*28, -5)), fill=pants, width=max(9, int(14*s)), joint="curve")
        else:
            for side in (-1, 1):
                swing = arm_swing * 8 if pose in ("talk", "think") else 0
                d.line((pt(side*10, hip_y), pt(side*16+swing, -24), pt(side*18+swing, 0)), fill=pants, width=max(9, int(14*s)), joint="curve")
    else:
        d.line((pt(-22, shoulder_y), pt(-40, -75), pt(-44, -42)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(22, shoulder_y), pt(40, -75), pt(44, -42)), fill=color, width=max(8, int(13*s)), joint="curve")
        d.line((pt(-10, hip_y), pt(-16, -24), pt(-18, 0)), fill=pants, width=max(9, int(14*s)))
        d.line((pt(10, hip_y), pt(16, -24), pt(18, 0)), fill=pants, width=max(9, int(14*s)))

    # Finish the silhouette with visible hands and shoes.
    if pose == "reach":
        hand_points = [pt(-48, -35), pt(95, -133)]
    elif pose == "jump":
        hand_points = [pt(-48, -166), pt(48, -166)]
    elif pose == "push":
        hand_points = [pt(-55, -48), pt(82, -112)]
    else:
        hand_points = [pt(-44, -42), pt(44, -42)]
    for hand_x, hand_y in hand_points:
        radius = max(5, int(8*s))
        d.ellipse((hand_x-radius, hand_y-radius, hand_x+radius, hand_y+radius), fill=skin)
    for side in (-1, 1):
        shoe_x, shoe_y = pt(side*18, -1)
        d.ellipse((shoe_x-10*s, shoe_y-4*s, shoe_x+10*s, shoe_y+5*s), fill=(24, 31, 42))


def draw_shadow(image: Image.Image, x: int, foot_y: int, t: float, opacity: float = 1.0) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sway = math.sin(t * 2.2) * 5
    d.ellipse((x-26+sway, foot_y-184, x+26+sway, foot_y-132), fill=(0, 0, 0, int(225*opacity)))
    d.line((x+sway, foot_y-134, x+sway, foot_y-48), fill=(0, 0, 0, int(235*opacity)), width=27)
    d.line((x+sway, foot_y-105, x-35+sway, foot_y-65), fill=(0, 0, 0, int(220*opacity)), width=15)
    d.line((x+sway, foot_y-105, x+42+sway, foot_y-86), fill=(0, 0, 0, int(220*opacity)), width=15)
    d.line((x+sway, foot_y-48, x-22+sway, foot_y), fill=(0, 0, 0, int(230*opacity)), width=18)
    d.line((x+sway, foot_y-48, x+24+sway, foot_y), fill=(0, 0, 0, int(230*opacity)), width=18)
    image.paste(Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB"))


def draw_caption(image: Image.Image, text: str, subtext: str = "") -> None:
    if not text:
        return
    d = ImageDraw.Draw(image)
    f = font(30, True)
    sf = font(17, False)
    # restrained editorial caption, not a full-screen template card
    d.rounded_rectangle((68, 54, 760, 139 if subtext else 112), radius=10, fill=(4, 8, 15))
    d.text((92, 69), text, font=f, fill=(237, 242, 247), stroke_width=1, stroke_fill=(3, 5, 9))
    if subtext:
        d.text((94, 111), subtext, font=sf, fill=(151, 190, 205))


def paint_environment_details(image: Image.Image, kind: str, t: float, opening: float = 0.0) -> None:
    """Add layered set dressing so locations read as places, not empty gradients."""
    d = ImageDraw.Draw(image, "RGBA")
    if kind == "trackside":
        d.ellipse((1027, 135, 1093, 201), fill=(205, 45, 38, 35))
        d.line((0, 445, W, 445), fill=(102, 119, 130, 100), width=2)
    elif kind == "platform":
        # Rain blowing across the open track end and reflected station lamps.
        for i in range(55):
            x = (i*71 + int(t*110)) % W
            y = 210 + (i*43) % 330
            d.line((x, y, x-4, y+17), fill=(125, 164, 185, 100), width=1)
        d.polygon([(0, 538), (W, 538), (W, 558), (0, 558)], fill=(211, 176, 91, 65))
    elif kind == "service_gate":
        d.rectangle((775, 150, 1165, 520), outline=(142, 157, 169, 170), width=4)
        d.text((805, 120), "MAINTENANCE ACCESS", font=font(17, True), fill=(184, 197, 204, 190))
    elif kind == "tunnel":
        d.ellipse((595, 310, 685, 400), fill=(219, 174, 91, 35))
        d.line((0, 540, W, 540), fill=(74, 91, 105, 130), width=3)
    elif kind == "exit":
        d.text((900, 105), "EXIT", font=font(24, True), fill=(194, 210, 204, 220))
    elif kind == "corridor":
        # Recessed wall panels, skirting, numbered doors and practical sconces.
        for x in (95, 365, 635, 905, 1175):
            d.rounded_rectangle((x-88, 168, x+88, 494), radius=5, outline=(75, 91, 110, 145), width=3)
            d.line((x-72, 185, x+72, 185), fill=(91, 108, 127, 110), width=2)
            d.rectangle((x-7, 205, x+7, 245), fill=(169, 190, 204, 85))
            d.ellipse((x+58, 345, x+65, 352), fill=(201, 161, 105, 180))
        # Low, warm practical light pools.
        for x in (260, 770, 1120):
            d.ellipse((x-100, 480, x+100, 555), fill=(175, 135, 83, 17))
    elif kind == "stairwell":
        d.line((105, 180, 105, 520), fill=(111, 128, 145, 190), width=9)
        d.line((105, 180, 470, 180), fill=(111, 128, 145, 190), width=8)
        for i in range(9):
            y = 260 + i*27
            x = 790 + i*37
            d.line((x, y, min(1180, x+250), y), fill=(91, 107, 125, 145), width=3)
        d.rectangle((140, 205, 260, 270), outline=(93, 114, 132, 130), width=3)
        d.text((164, 220), "B2", font=font(26, True), fill=(163, 183, 198, 170))
    elif kind == "rainroom":
        # Condensation streaks and a cold window reflection.
        for i in range(18):
            x = 930 + (i*37)%245
            y = 165 + (i*59)%320
            d.line((x, y, x-3, y+35+(i%4)*12), fill=(133, 177, 198, 80), width=2)
        d.rectangle((940, 175, 1170, 490), outline=(125, 161, 181, 130), width=2)
    elif kind == "street":
        # Storefront signage, lamp posts, wet pavement reflections.
        d.rectangle((100, 175, 270, 225), fill=(10, 16, 25, 220), outline=(116, 139, 157, 130), width=2)
        d.text((117, 186), "NIGHT SHOP", font=font(17, True), fill=(183, 199, 209, 210))
        d.line((720, 120, 720, 505), fill=(75, 91, 108, 210), width=7)
        d.ellipse((695, 105, 745, 135), fill=(196, 166, 112, 185))
        for x in (180, 430, 930, 1110):
            d.polygon([(x-48, 526), (x+48, 526), (x+100, 615), (x-100, 615)], fill=(79, 112, 133, 24))
    elif kind == "ship":
        d.arc((110, 110, 1170, 640), 185, 355, fill=(108, 132, 148, 170), width=8)
        for x in (180, 430, 850, 1100):
            d.ellipse((x-25, 220, x+25, 270), outline=(156, 179, 190, 190), width=5)
            d.ellipse((x-12, 233, x+12, 257), fill=(102, 157, 178, 90))
        d.rectangle((80, 430, 1200, 445), fill=(70, 89, 105, 130))
        d.text((100, 455), "DECK 03  /  RESTRICTED", font=font(16, True), fill=(148, 173, 188, 190))
    elif kind == "laboratory":
        # A clear science-lab set: workbench, glass panels, monitors and indicator lights.
        d.rectangle((70, 155, 410, 430), fill=(9, 23, 37, 190), outline=(102, 159, 187, 185), width=4)
        d.rectangle((95, 180, 385, 355), fill=(18, 48, 67, 220), outline=(80, 151, 181, 190), width=3)
        d.line((115, 215, 360, 215), fill=(83, 192, 206, 180), width=4)
        d.line((115, 250, 315, 250), fill=(91, 143, 175, 150), width=3)
        d.rectangle((830, 160, 1190, 430), fill=(8, 22, 36, 190), outline=(102, 159, 187, 185), width=4)
        for i in range(5):
            xx=865+i*62
            d.ellipse((xx, 190, xx+18, 208), fill=(73, 207, 171, 210) if i%2==0 else (236, 187, 84, 190))
            d.line((xx+8, 225, xx+8, 380), fill=(69, 130, 158, 100), width=2)
        d.polygon([(130, 485), (1150, 485), (1210, 565), (70, 565)], fill=(31, 57, 75, 220))
        d.line((110, 485, 1170, 485), fill=(122, 175, 194, 210), width=5)
    elif kind == "forest":
        for i in range(13):
            x = (i*113 + 25) % W
            width = 22 + (i%3)*13
            d.polygon([(x-width, 520), (x-8, 130+(i%4)*28), (x+width, 520)], fill=(8, 22, 23, 205))
            d.line((x, 250, x-65, 330), fill=(19, 42, 39, 200), width=9)
            d.line((x, 310, x+58, 370), fill=(19, 42, 39, 200), width=8)
        d.ellipse((420, 180, 860, 610), fill=(139, 170, 124, 12))
    # A fine film-grain pass, deterministic per frame.
    rng = random.Random(int(t*24)+991)
    for _ in range(650):
        x, y = rng.randrange(W), rng.randrange(22, H-22)
        c = 255 if rng.random() > .5 else 0
        d.point((x, y), fill=(c, c, c, 12))


def facing_sign(value: Any) -> int:
    """Accept numeric directions and natural-language AI directions."""
    if isinstance(value, str):
        direction = value.strip().lower()
        if direction in {"left", "west", "-1", "backward", "backwards"}:
            return -1
        if direction in {"right", "east", "1", "forward", "forwards"}:
            return 1
    try:
        return -1 if float(value) < 0 else 1
    except (TypeError, ValueError):
        return 1


def draw_character_design(image: Image.Image, actor: dict[str, Any], pose_data: dict[str, Any]) -> None:
    """Add readable wardrobe, hair and facial expression to the base skeleton."""
    x, y = float(pose_data.get("x", 640)), float(pose_data.get("y", 610))
    scale = float(actor.get("scale", 1.0))
    facing = facing_sign(pose_data.get("facing", 1))
    wardrobe = actor.get("wardrobe", "hoodie")
    accent = tuple(actor.get("accent_rgb", [87, 151, 177]))
    d = ImageDraw.Draw(image)
    # Clothing follows the torso; it remains intentionally graphic and readable.
    if wardrobe == "coat":
        d.polygon([(x-19*scale, y-111*scale), (x+19*scale, y-111*scale),
                   (x+27*scale, y-54*scale), (x+15*scale, y-45*scale),
                   (x-15*scale, y-45*scale), (x-27*scale, y-54*scale)],
                  fill=(35, 48, 63), outline=accent)
        d.line((x, y-105*scale, x+3*scale, y-49*scale), fill=(150, 165, 177), width=max(2,int(3*scale)))
    elif wardrobe == "hoodie":
        d.arc((x-27*scale, y-145*scale, x+27*scale, y-92*scale), 180, 360, fill=accent, width=max(3,int(5*scale)))
        d.line((x-17*scale, y-101*scale, x-23*scale, y-58*scale), fill=accent, width=max(3,int(4*scale)))
        d.line((x+17*scale, y-101*scale, x+23*scale, y-58*scale), fill=accent, width=max(3,int(4*scale)))
    # Hair silhouette and eyebrows distinguish the character from a blank circle.
    hx, hy = int(x), int(y-145*scale)
    hair = actor.get("hair", "short")
    hair_color = tuple(actor.get("hair_rgb", [29,31,37]))
    if hair == "long":
        d.pieslice((hx-30*scale, hy-32*scale, hx+30*scale, hy+30*scale), 180, 350, fill=hair_color)
        d.ellipse((hx-31*scale, hy-5*scale, hx-18*scale, hy+45*scale), fill=hair_color)
    elif hair == "white":
        d.pieslice((hx-31*scale, hy-35*scale, hx+31*scale, hy+24*scale), 180, 360, fill=hair_color)
        d.ellipse((hx-33*scale,hy-10*scale,hx-20*scale,hy+20*scale),fill=hair_color)
    elif hair == "side_part":
        d.pieslice((hx-31*scale, hy-34*scale, hx+31*scale, hy+21*scale), 180, 360, fill=hair_color)
        d.line((hx-3*scale,hy-30*scale,hx+19*scale,hy-27*scale),fill=(220,220,220),width=max(1,int(2*scale)))
    elif hair == "cap":
        d.pieslice((hx-31*scale, hy-35*scale, hx+31*scale, hy+22*scale), 180, 360, fill=hair_color)
        d.line((hx, hy-28*scale, hx+30*scale*facing, hy-19*scale), fill=accent, width=max(2,int(4*scale)))
    else:
        d.arc((hx-30*scale, hy-32*scale, hx+30*scale, hy+18*scale), 185, 355, fill=hair_color, width=max(5,int(9*scale)))
    expression = actor.get("expression", "neutral")
    eye_y = hy-4*scale
    eye_x = hx+facing*10*scale
    if expression == "fear":
        d.ellipse((eye_x-4*scale, eye_y-4*scale, eye_x+4*scale, eye_y+4*scale), fill=(12,19,28))
        d.arc((hx-11*scale, hy+5*scale, hx+11*scale, hy+22*scale), 190, 350, fill=(55,25,29), width=2)
    elif expression == "determined":
        d.line((eye_x-5*scale, eye_y-5*scale, eye_x+5*scale, eye_y-2*scale), fill=(23,31,40), width=3)
    elif expression in {"happy", "joy", "smile"}:
        d.arc((hx-12*scale, hy+2*scale, hx+12*scale, hy+20*scale), 10, 170, fill=(105,48,48), width=max(2,int(3*scale)))
    elif expression in {"curious", "think", "thinking"}:
        d.ellipse((eye_x-4*scale, eye_y-4*scale, eye_x+4*scale, eye_y+4*scale), fill=(18,25,34))
        d.line((eye_x-5*scale,eye_y-9*scale,eye_x+5*scale,eye_y-11*scale),fill=(50,42,38),width=2)
    if actor.get("age_variant") == "elderly":
        d.arc((hx-18*scale,hy+5*scale,hx-3*scale,hy+15*scale),180,350,fill=(125,93,77),width=1)
        d.arc((hx+3*scale,hy+5*scale,hx+18*scale,hy+15*scale),190,360,fill=(125,93,77),width=1)
        if "walking_stick" in actor.get("accessories",[]):
            d.line((x+34*scale,y-75*scale,x+43*scale,y+2*scale),fill=(116,82,48),width=max(3,int(5*scale)))
            d.arc((x+29*scale,y-84*scale,x+49*scale,y-64*scale),180,360,fill=(116,82,48),width=max(3,int(4*scale)))


def make_frame(script: dict[str, Any], scene: dict[str, Any], local_t: float, global_t: float, bg_cache: dict[str, Image.Image]) -> Image.Image:
    raw_environment = scene.get("environment", "corridor")
    # AI planners may return a structured environment manifest rather than a
    # renderer key. Resolve it to a supported key without discarding the plan.
    if isinstance(raw_environment, dict):
        kind = (raw_environment.get("type") or raw_environment.get("name") or
                raw_environment.get("id") or raw_environment.get("location") or "forest")
    else:
        kind = raw_environment
    if not isinstance(kind, str):
        kind = "forest"
    kind = kind.strip().lower().replace(" ", "_") or "forest"
    if kind not in bg_cache:
        bg_cache[kind] = gradient_background(kind)
    image = render_environment_background(bg_cache[kind].copy(), kind, scene)
    opening = float(scene.get("door_open", 0.0))
    paint_environment_details(image, kind, global_t, opening)
    image = animate_environment(image, kind, scene, global_t)
    # A soft moving pool of light and a subtle practical flicker.
    d = ImageDraw.Draw(image)
    flicker = 0.92 + 0.08 * math.sin(global_t * 13.0)
    if kind not in ("platform", "service_gate", "tunnel", "exit", "trackside", "forest", "road",
                    "laboratory", "bedroom", "home", "living_room", "house", "classroom",
                    "school", "office", "workplace", "park", "garden", "beach", "ocean",
                    "sea", "underwater"):
        d.polygon([(640, 130), (930, 130), (1120, 530), (430, 530)], fill=(40, 55, 72))
        d.line((640, 130, 430, 530), fill=(49, 65, 82), width=2)
        d.line((930, 130, 1120, 530), fill=(49, 65, 82), width=2)
    glow = float(scene.get("door_glow", 0.0)) * flicker
    if kind == "corridor" and (opening > 0 or glow > 0):
        draw_door(d, opening, glow)
    # Environmental motion: drifting dust or rainfall.
    rng = random.Random(int(global_t * 24) + 811)
    for i in range(28):
        px = (i * 97 + int(global_t * (8 + i % 5))) % W
        py = (i * 53 + int(global_t * (3 + i % 4))) % 570
        d.ellipse((px, py, px+2, py+2), fill=(79, 102, 126))
    if kind in ("platform", "street", "rainroom") or (kind in ("forest", "road") and scene.get("weather") == "rain"):
        for i in range(75 if kind == "rainroom" else 42):
            px = (i * 41 + int(global_t * 95)) % W
            py = (i * 67 + int(global_t * 220)) % H
            d.line((px, py, px-5, py+15), fill=(86, 126, 154), width=1)
    if scene.get("shadow"):
        sx = int(scene.get("shadow_x", 990))
        opacity = float(scene.get("shadow_opacity", 1.0)) * min(1.0, max(0.0, local_t * 2))
        draw_shadow(image, sx, 526, global_t, opacity)
    # Render a cast, not just one hard-coded protagonist. Each species is
    # dispatched to its own anatomy rig; humans keep the existing human rig.
    cast = scene.get("actors", [])
    primary = scene.get("actor")
    if primary:
        cast = [primary] + [a for a in cast if a is not primary]
    for actor in cast:
        actor = dict(actor)
        if str(actor.get("species", "human")).lower() in {"human", "boy", "girl", "man", "woman", "old_man"}:
            cid = str(actor.get("character_id", "man_1"))
            if cid in HUMAN_CAST:
                actor = {**character_profile(cid), **actor}
            if actor.get("age_variant") in {"elderly", "old", "senior"}:
                actor = apply_age_variant(actor, "elderly")
        pose_data = sample_keyframes(actor.get("keyframes", []), local_t)
        pose_data["facing"] = facing_sign(pose_data.get("facing", 1))
        pose_data["ground_y"] = float(pose_data.get("y", 610))
        pose_data["action_progress"] = local_t
        actor["_motion"] = motion_for_actor(actor, local_t, str(pose_data.get("pose", "idle")) )
        if str(pose_data.get("pose", "idle")).lower() == "jump":
            pose_data["y"] = float(pose_data["y"]) - 54.0 * math.sin(math.pi * local_t)
        actor["_ground_y"] = pose_data["ground_y"]
        species = str(actor.get("species", "human")).lower()
        if not draw_species_character(image, actor, pose_data, global_t):
            draw_character(
                image, float(pose_data.get("x", 640)), float(pose_data.get("y", 610)),
                str(pose_data.get("pose", "idle")), int(pose_data.get("facing", 1)),
                global_t, float(actor.get("scale", 1.0)), actor,
            )
            draw_character_design(image, actor, pose_data)
    draw_stickers(image, scene, local_t)
    caption = scene.get("caption", "")
    sub = scene.get("subcaption", "")
    # Fade captions in and out at shot boundaries.
    fade = min(1.0, local_t * 5.0, (1.0 - local_t) * 5.0)
    if caption and fade > 0:
        draw_caption(image, caption, sub)
    # Story-aware camera: focus, smooth push-in and subject tracking.
    image = apply_camera(image, scene, local_t)
    return image.convert("RGB")


def write_ambience(path: Path, duration: float, sample_rate: int = 22050) -> None:
    total = int(duration * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        chunk = bytearray()
        for n in range(total):
            t = n / sample_rate
            fade = min(1.0, t * 1.5, max(0.0, (duration - t) * 2.0))
            drone = 0.11 * math.sin(2 * math.pi * 48 * t) + 0.035 * math.sin(2 * math.pi * 73 * t)
            pulse_phase = t % 1.08
            pulse = 0.0
            if pulse_phase < 0.18:
                pulse = math.sin(math.pi * pulse_phase / 0.18) ** 3 * (1 - pulse_phase / 0.18)
            thump = 0.15 * pulse * math.sin(2 * math.pi * (58 - 18 * pulse_phase) * t)
            shimmer = 0.018 * math.sin(2 * math.pi * (220 + 18 * math.sin(t * 0.7)) * t)
            value = max(-0.85, min(0.85, (drone + thump + shimmer) * fade))
            sample = int(value * 32767)
            chunk.extend((sample.to_bytes(2, "little", signed=True)) * 2)
            if len(chunk) >= 65536:
                wav.writeframesraw(chunk)
                chunk.clear()
        if chunk:
            wav.writeframesraw(chunk)


def render(script_path: Path, output: Path) -> Path:
    script = json.loads(script_path.read_text(encoding="utf-8"))
    validate_script(script)
    raw_size = script.get("size", [W, H])
    if isinstance(raw_size, dict):
        raw_size = [raw_size.get("width", W), raw_size.get("height", H)]
    if not isinstance(raw_size, (list, tuple)) or len(raw_size) != 2:
        raise ValueError("Script size must be [width, height] or {width, height}")
    try:
        width, height = int(raw_size[0]), int(raw_size[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("Script canvas width and height must be numeric") from exc
    if [width, height] != [W, H]:
        raise ValueError(f"This build currently renders at {W}x{H}; script size must match.")
    fps = int(script.get("fps", FPS))
    duration = float(script["duration"])
    output.parent.mkdir(parents=True, exist_ok=True)
    poster_path = output.with_name(output.stem + "-poster.png")
    with tempfile.TemporaryDirectory(prefix="stick-animate-") as temp_dir:
        audio_path = Path(temp_dir) / "scene-audio.wav"
        audio_cues = render_audio(script, audio_path)
        if os.environ.get("STICK_ANIMATE_OFFLINE_AUDIO") != "1":
            attribution_path = output.parent / "sound-effect-attribution.json"
            found = find_and_mix_effects(
                audio_path, audio_cues, duration,
                output.parent / "sound-effects", attribution_path,
            )
            print(f"Found and mixed {len(found)} licensed sound-effect clips.")
        (output.parent / "audio-cues.json").write_text(json.dumps(audio_cues, indent=2), encoding="utf-8")
        understanding = analyse_script(script)
        (output.parent / "scene-understanding.json").write_text(json.dumps(understanding, indent=2), encoding="utf-8")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
            "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-shortest", "-movflags", "+faststart", str(output),
        ]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        bg_cache: dict[str, Image.Image] = {}
        total_frames = int(round(duration * fps))
        try:
            assert process.stdin is not None
            for frame_no in range(total_frames):
                t = frame_no / fps
                scene = next(s for s in script["scenes"] if float(s["start"]) <= t < float(s["end"]))
                span = float(scene["end"]) - float(scene["start"])
                local_t = min(1.0, max(0.0, (t - float(scene["start"])) / span))
                frame = make_frame(script, scene, local_t, t, bg_cache)
                # Blend the new shot in smoothly for the configured transition window.
                scene_index = script["scenes"].index(scene)
                trans_len = transition_duration(script, scene)
                if scene_index > 0 and trans_len > 0 and local_t * span < trans_len:
                    prior = script["scenes"][scene_index - 1]
                    prior_span = float(prior["end"]) - float(prior["start"])
                    prior_t = max(0.0, min(1.0, (float(prior["end"]) - 0.001 - float(prior["start"])) / prior_span))
                    prior_frame = make_frame(script, prior, prior_t, float(prior["end"]) - 0.001, bg_cache)
                    frame = crossfade(frame, prior_frame, (local_t * span) / trans_len)
                if frame_no == total_frames // 2:
                    frame.save(poster_path, quality=95)
                process.stdin.write(frame.tobytes())
            process.stdin.close()
            error = process.stderr.read() if process.stderr else b""
            code = process.wait()
            if code != 0:
                raise RuntimeError("FFmpeg render failed: " + error.decode("utf-8", "replace")[-4000:])
        except (BrokenPipeError, OSError):
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            error = process.stderr.read() if process.stderr else b""
            process.wait()
            raise RuntimeError("Video encoder stopped unexpectedly: " + error.decode("utf-8", "replace")[-4000:])
    if not output.exists() or output.stat().st_size < 100_000:
        raise RuntimeError("MP4 was not created or is unexpectedly small")
    print(f"Rendered {output} ({output.stat().st_size:,} bytes)")
    print(f"Poster: {poster_path}")
    return poster_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Design and render a multi-scene 2D animated video.")
    parser.add_argument("--script", type=Path, default=Path("demo/mystery_hallway.json"))
    parser.add_argument("--story-file", type=Path, help="Plain-text story; Scene Designer will create a multi-shot plan.")
    parser.add_argument("--duration", type=float, default=None, help="Optional reference duration; ignored in auto mode.")
    parser.add_argument("--duration-mode", choices=("auto", "strict"), default="auto", help="Auto follows story pacing; strict enforces --duration.")
    parser.add_argument("--title", default="Untitled Story", help="Video title when using --story-file.")
    parser.add_argument("--output", type=Path, default=Path("output/mystery-hallway.mp4"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    script_path = args.script
    if args.story_file:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        script_path = args.output.parent / (args.output.stem + "-scene-plan.json")
        plan = design_production(args.story_file.read_text(encoding="utf-8"), args.duration, args.title, duration_mode=args.duration_mode)
        script_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"Scene Designer created {len(plan['scenes'])} shots: {script_path}")
    data = json.loads(script_path.read_text(encoding="utf-8"))
    validate_script(data)
    if args.validate_only:
        print(f"Script valid: {len(data['scenes'])} scenes, {data['duration']} seconds.")
    else:
        render(script_path, args.output)


if __name__ == "__main__":
    main()
