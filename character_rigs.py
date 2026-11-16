from __future__ import annotations

"""Species-specific procedural 2D character rigs.

These are independent anatomy systems, not human skeletons with animal labels.
They are a first procedural rig layer intended for later sprite/mesh assets.
"""
import math
from typing import Any
from PIL import Image, ImageDraw


def _rgb(value: Any, default: tuple[int, int, int]) -> tuple[int, int, int]:
    try:
        parts = tuple(max(0, min(255, int(v))) for v in value)
        return parts if len(parts) == 3 else default
    except (TypeError, ValueError):
        return default


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]],
          fill: tuple[int, int, int], width: int) -> None:
    draw.line([(int(x), int(y)) for x, y in points], fill=fill, width=max(2, width), joint="curve")


def draw_species_character(image: Image.Image, actor: dict[str, Any],
                           pose: dict[str, Any], t: float) -> bool:
    """Draw a non-human character using a species-specific body plan.

    Supported: monkey, turtle, bear, dog, cat, bird, fish and dinosaur; human uses the fallback rig.
    """
    species = str(actor.get("species", "human")).lower()
    if species in ("human", "boy", "girl", "man", "woman", "old-man", "old_man"):
        return False
    if species not in ("monkey", "turtle", "bear", "dog", "cat", "bird", "fish", "dinosaur", "trex", "t-rex"):
        return False

    d = ImageDraw.Draw(image)
    x, y = float(pose.get("x", 640)), float(pose.get("y", 610))
    scale = max(0.25, min(3.0, float(actor.get("scale", 1.0))))
    facing = 1 if int(pose.get("facing", 1)) >= 0 else -1
    phase = t * (10.0 if pose.get("pose") in ("run", "walk", "swim", "fly") else 2.0)
    default_coats = {
        "monkey": (151, 96, 59), "turtle": (104, 151, 91), "bear": (132, 91, 63),
        "dog": (174, 133, 94), "cat": (174, 133, 94),
    }
    coat = _rgb(actor.get("body_rgb"), default_coats.get(species, (190, 203, 211)))
    dark = _rgb(actor.get("marking_rgb"), (58, 49, 43))
    eye = (18, 24, 30)

    def p(dx: float, dy: float) -> tuple[int, int]:
        return int(x + facing * dx * scale), int(y + dy * scale)

    def ellipse(cx: float, cy: float, rx: float, ry: float, fill: tuple[int, int, int],
                outline: tuple[int, int, int] | None = None, width: int = 2) -> None:
        a, b = p(cx-rx, cy-ry); c, e = p(cx+rx, cy+ry)
        # Mirroring x reverses endpoints; Pillow accepts normalized boxes.
        d.ellipse((min(a,c), min(b,e), max(a,c), max(b,e)), fill=fill, outline=outline, width=width)

    if species == "monkey":
        # Upright primate with long limbs, expressive face and curling tail.
        bob = math.sin(phase * 2) * (4 if pose.get("pose") in ("run", "walk", "jump") else 1.5)
        ellipse(0, -65+bob, 34, 48, coat, dark, 3)
        ellipse(0, -132+bob, 34, 34, coat, dark, 3)
        ellipse(-31, -137+bob, 11, 14, coat, dark, 2)
        ellipse(31, -137+bob, 11, 14, coat, dark, 2)
        ellipse(13, -124+bob, 20, 13, (205, 157, 116), dark, 2)
        ellipse(21, -128+bob, 3, 4, eye)
        ellipse(-11, -143+bob, 4, 5, eye)
        ellipse(11, -143+bob, 4, 5, eye)
        stride = math.sin(phase)
        arm_swing = 24 if pose.get("pose") in ("run", "walk", "reach") else 7
        for side in (-1, 1):
            shoulder = p(side*23, -96+bob)
            elbow = p(side*31 + side*stride*arm_swing, -63+bob)
            hand = p(side*38 + side*stride*arm_swing, -42+bob)
            _line(d, [shoulder, elbow, hand], coat, max(6, int(11*scale)))
            hip = p(side*17, -35+bob)
            knee = p(side*22 - stride*side*19, -16)
            foot = p(side*25 - stride*side*27, -1)
            _line(d, [hip, knee, foot], coat, max(7, int(13*scale)))
        tail_wave = math.sin(t*4.5)*18
        _line(d, [p(-25,-78+bob), p(-55,-66+tail_wave), p(-70,-91+tail_wave), p(-55,-111+tail_wave)], dark, max(5,int(8*scale)))
    elif species == "turtle":
        # Low quadruped with a domed shell, small head and four articulated feet.
        bob = math.sin(phase*2)*2 if pose.get("pose") in ("walk", "run") else 0
        ellipse(-3, -47+bob, 58, 35, dark, (38, 83, 58), 4)
        ellipse(-3, -50+bob, 48, 28, (83, 132, 83), dark, 3)
        for dx in (-25, 0, 20):
            d.line((int(x+facing*(dx-9)*scale), int(y-66*scale+bob),
                    int(x+facing*(dx+9)*scale), int(y-34*scale+bob)),
                   fill=(48, 91, 62), width=max(2,int(3*scale)))
        ellipse(48, -59+bob, 27, 22, coat, dark, 3)
        ellipse(63, -65+bob, 3, 4, eye)
        stride = math.sin(phase)
        for side in (-1, 1):
            for front in (-1, 1):
                dx = (35 if front > 0 else -39) + side*9
                swing = math.sin(phase + (0 if front == side else math.pi))*7 if pose.get("pose") in ("walk", "run") else 0
                _line(d, [p(dx,-31+bob), p(dx+swing,-12), p(dx+swing+4,-2)], coat, max(7,int(12*scale)))
                ellipse(dx+swing+4,-2,9,5,dark)
    elif species == "bear":
        # Heavy quadrupedal bear with broad shoulders, muzzle, rounded ears and paws.
        bob = math.sin(phase*2)*2.5 if pose.get("pose") in ("walk", "run") else 0
        ellipse(-2, -63+bob, 67, 48, coat, dark, 4)
        ellipse(42, -111+bob, 39, 36, coat, dark, 3)
        ellipse(18, -143+bob, 12, 13, coat, dark, 2)
        ellipse(62, -142+bob, 12, 13, coat, dark, 2)
        ellipse(72, -98+bob, 21, 15, (191, 151, 119), dark, 2)
        ellipse(84, -102+bob, 5, 4, dark)
        ellipse(49, -122+bob, 4, 5, eye)
        stride = math.sin(phase)
        for side, offset in ((-1,0.0),(1,math.pi)):
            swing = math.sin(phase+offset)*13 if pose.get("pose") in ("walk", "run", "push") else 0
            dx = 38 if side == 1 else -42
            _line(d, [p(dx,-45+bob), p(dx+swing,-20), p(dx+swing,-2)], coat, max(9,int(17*scale)))
            ellipse(dx+swing,-1,13,7,dark)
    elif species in ("dog", "cat"):
        # Four-legged spine, shoulder/hip joints, articulated limbs, muzzle and tail.
        bob = math.sin(phase*2) * (3 if pose.get("pose") in ("run", "walk") else 1.5)
        body_y = -47 + bob
        ellipse(-2, body_y, 65, 29, coat, dark, 3)
        ellipse(42, -79+bob, 28, 27, coat, dark, 3)
        # Breed silhouette details: canine muzzle and floppy/pointed ears.
        if species == "dog":
            ellipse(65, -67+bob, 23, 15, coat, dark, 2)
            ellipse(83, -68+bob, 5, 4, dark)
            ellipse(35, -105+bob, 13, 21, dark)
        else:
            d.polygon([p(24,-97+bob), p(29,-132+bob), p(48,-105+bob)], fill=dark)
            d.polygon([p(49,-103+bob), p(64,-131+bob), p(67,-91+bob)], fill=dark)
            ellipse(65, -74+bob, 16, 12, coat)
            _line(d, [p(55,-47), p(76,-35), p(88,-51), p(79,-69)], dark, max(3,int(7*scale)))
        ellipse(49, -85+bob, 4, 5, eye)
        # Tail wag / alert tail.
        wag = math.sin(t*8)*12
        if species == "dog":
            _line(d, [p(-60,body_y), p(-82,-61+wag), p(-91,-83+wag)], coat, max(6,int(12*scale)))
        # Alternating fore/hind leg swing with knee/hock articulation.
        stride = math.sin(phase)
        for side, offset in ((-1,0.0),(1,math.pi)):
            swing = math.sin(phase+offset)*19 if pose.get("pose") in ("run","walk") else 0
            hip_x = 30 if side == 1 else -35
            leg_top = p(hip_x, body_y+9)
            knee = p(hip_x+swing*0.45, -19+bob)
            paw = p(hip_x+swing, -2)
            _line(d,[leg_top,knee,paw],coat,max(7,int(13*scale)))
            ellipse(hip_x+swing,-2,10,5,dark)
    elif species == "bird":
        # Feathered torso, beak, independent wings and two legs.
        bob = math.sin(phase*2)*3 if pose.get("pose") in ("fly","flap") else math.sin(t*2)*1.5
        ellipse(0,-48+bob,43,31,coat,dark,3)
        ellipse(24,-82+bob,25,23,coat,dark,2)
        d.polygon([p(45,-83+bob),p(72,-74+bob),p(47,-66+bob)], fill=(220,157,65))
        ellipse(32,-88+bob,4,5,eye)
        flap = math.sin(t*13)*27 if pose.get("pose") in ("fly","flap") else math.sin(t*2)*4
        _line(d,[p(-3,-58+bob),p(-28,-75-flap),p(-51,-56-flap)],dark,max(5,int(10*scale)))
        _line(d,[p(2,-54+bob),p(-23,-42+flap),p(-48,-49+flap)],coat,max(5,int(10*scale)))
        for dx in (-12,18):
            _line(d,[p(dx,-20),p(dx-2,-5),p(dx-10,-1)],(204,151,67),max(3,int(5*scale)))
    elif species == "fish":
        # Horizontal aquatic body with tail fin, pectoral fin, gill and moving tail.
        tail = math.sin(t*9)*15
        ellipse(0,-55,64,34,coat,dark,3)
        d.polygon([p(-55,-55),p(-91,-84+tail),p(-88,-25+tail)], fill=dark, outline=coat)
        d.polygon([p(-4,-83),p(20,-111),p(30,-77)], fill=dark)
        d.polygon([p(-2,-29),p(26,-2),p(35,-37)], fill=dark)
        ellipse(43,-67,5,6,eye)
        for gx in (17,25,33):
            d.arc((int(x+facing*(gx+2)*scale-7*scale),int(y-75*scale),
                   int(x+facing*(gx+16)*scale),int(y-37*scale)),90,260,fill=dark,width=max(2,int(2*scale)))
    else:
        # Dinosaur: powerful biped, long balancing tail, large skull and tiny forearms.
        tail_sway = math.sin(t*2.5)*8
        ellipse(0,-75,55,42,coat,dark,4)
        ellipse(43,-124,36,27,coat,dark,3)
        d.polygon([p(64,-117),p(103,-108),p(72,-95)],fill=coat,outline=dark)
        ellipse(62,-133,5,5,eye)
        _line(d,[p(-42,-78),p(-78,-67+tail_sway),p(-119,-88+tail_sway)],coat,max(9,int(17*scale)))
        _line(d,[p(25,-96),p(4,-70),p(15,-58)],dark,max(4,int(7*scale)))
        stride = math.sin(phase)
        for side in (-1,1):
            hip = p(side*22,-46)
            knee = p(side*25+stride*side*9,-22)
            foot = p(side*27+stride*side*16,-1)
            _line(d,[hip,knee,foot],coat,max(10,int(19*scale)))
            _line(d,[foot,p(side*42+stride*side*16,0)],dark,max(4,int(8*scale)))
        # Back ridge / small dorsal plates.
        for i in range(5):
            xx=-25+i*17
            d.polygon([p(xx,-105),p(xx+7,-119),p(xx+14,-101)],fill=dark)

    # A consistent contact shadow anchors every species to its environment.
    ellipse(0,2,48 if species not in ("bird","fish") else 34,5,(4,7,11))
    return True


def available_species() -> tuple[str, ...]:
    return ("human", "monkey", "turtle", "bear", "dog", "cat", "bird", "fish", "dinosaur")
