from __future__ import annotations

"""Species-specific procedural 2D character and prop rigs.

Motion is deliberately species-dependent: each animal has its own gait rate,
stride, body bounce and action silhouette. This remains a procedural renderer,
not a frame-by-frame hand-drawn animation system.
"""
import math
from typing import Any
from PIL import Image, ImageDraw
from native_artwork import draw_native_character


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
    """Draw an animal rig or a simple story prop. Humans use the fallback rig."""
    species = str(actor.get("species", "human")).lower().replace("-", "_")
    supported = {"monkey", "turtle", "bear", "dog", "cat", "bird", "fish",
                 "dinosaur", "trex", "t_rex", "elephant", "deer", "fox", "rabbit", "fallen_tree", "apple_cluster", "apple"}
    if species in {"human", "boy", "girl", "man", "woman", "old_man"}:
        return False
    if species not in supported:
        # Unknown species receive an anatomy-aware native rig, never a generic human.
        return draw_native_character(image, actor, pose, t)

    d = ImageDraw.Draw(image)
    x, y = float(pose.get("x", 640)), float(pose.get("y", 610))
    scale = max(0.2, min(3.0, float(actor.get("scale", 1.0))))
    facing_value = pose.get("facing", 1)
    facing = -1 if str(facing_value).lower() in {"left", "west", "-1"} else ( -1 if isinstance(facing_value, (int, float)) and facing_value < 0 else 1)
    action = str(pose.get("pose", "idle")).lower()
    duration = max(0.0, min(1.0, float(pose.get("action_progress", (t % 1.6) / 1.6))))
    action_wave = math.sin(math.pi * duration)

    def p(dx: float, dy: float) -> tuple[int, int]:
        return int(x + facing * dx * scale), int(y + dy * scale)

    def ellipse(cx: float, cy: float, rx: float, ry: float, fill: tuple[int, int, int],
                outline: tuple[int, int, int] | None = None, width: int = 2) -> None:
        a, b = p(cx-rx, cy-ry); c, e = p(cx+rx, cy+ry)
        d.ellipse((min(a,c), min(b,e), max(a,c), max(b,e)), fill=fill, outline=outline, width=width)

    # Props share the same draw dispatch, so they are actually visible in the shot.
    if species == "fallen_tree":
        length = float(actor.get("length", 570)) * scale
        thickness = float(actor.get("thickness", 36)) * scale
        angle = math.radians(float(actor.get("angle", -4)))
        dx, dy = math.cos(angle) * length / 2, math.sin(angle) * length / 2
        _line(d, [(x-dx, y-dy), (x+dx, y+dy)], (105, 68, 42), max(12, int(thickness)))
        _line(d, [(x-dx, y-dy-5), (x+dx, y+dy-5)], (157, 111, 68), max(4, int(thickness*.35)))
        for side in (-1, 1):
            bx = x + side * dx
            by = y + side * dy
            d.ellipse((bx-18*scale, by-18*scale, bx+18*scale, by+18*scale), fill=(119, 78, 48), outline=(70, 48, 32), width=3)
        return True
    if species in {"apple", "apple_cluster"}:
        count = max(1, min(12, int(actor.get("count", 5))))
        for i in range(count):
            ax = x + ((i % 4) - 1.5) * 24 * scale
            ay = y - (i // 4) * 18 * scale + math.sin(t*3+i)*2
            r = 10 * scale
            d.ellipse((ax-r, ay-r, ax+r, ay+r), fill=(190, 48+i%2*18, 43), outline=(91, 43, 31), width=2)
            d.line((ax, ay-r, ax+2*scale, ay-r-7*scale), fill=(79, 65, 38), width=2)
            d.ellipse((ax+1*scale, ay-r-8*scale, ax+10*scale, ay-r-3*scale), fill=(76, 133, 65))
        return True

    defaults = {"monkey": (151,96,59), "turtle": (104,151,91), "bear": (132,91,63),
                "dog": (174,133,94), "cat": (174,133,94), "elephant": (145,151,158), "deer": (166,119,76), "fox": (205,105,43), "rabbit": (222,216,205)}
    coat = _rgb(actor.get("body_rgb"), defaults.get(species, (190,203,211)))
    dark = _rgb(actor.get("marking_rgb"), (58,49,43))
    eye = (18,24,30)

    # Each species has a deliberately different gait frequency and weight.
    rates = {"monkey": 11.5, "turtle": 3.1, "bear": 5.0, "dog": 8.5,
             "cat": 9.5, "bird": 7.0, "fish": 8.0, "dinosaur": 6.0,
             "trex": 6.0, "elephant": 3.2, "deer": 8.0, "fox": 8.8, "rabbit": 10.0}
    gait_active = action in {"walk", "run", "jump", "fly", "swim"}
    phase = float(pose.get("gait_phase", t * rates.get(species, 7.0))) * (1.35 if action == "run" else 1.0)
    stride = math.sin(phase)
    lean = float(pose.get("body_lean", 0.0))
    bob_control = float(pose.get("body_bob", 0.0))
    heavy_bob = math.sin(phase*2) * (1.8 if species == "bear" else 1.0)
    if action == "push":
        lean += 12 * action_wave
    elif action in {"reach", "pick_up"}:
        lean += 7 * action_wave
    jump_lift = 32 * max(0.0, math.sin(math.pi * duration)) if action == "jump" else 0.0
    y -= jump_lift + bob_control

    if species == "monkey":
        bob = math.sin(phase*2) * (5 if gait_active else 1.5)
        ellipse(0, -65+bob-lean*.25, 34, 48, coat, dark, 3)
        ellipse(0, -132+bob-lean*.35, 34, 34, coat, dark, 3)
        ellipse(-31,-137+bob,11,14,coat,dark,2); ellipse(31,-137+bob,11,14,coat,dark,2)
        ellipse(13,-124+bob,20,13,(205,157,116),dark,2)
        ellipse(21,-128+bob,3,4,eye); ellipse(-11,-143+bob,4,5,eye); ellipse(11,-143+bob,4,5,eye)
        arm = 29 if action in {"run","jump","reach"} else 9
        for side in (-1,1):
            swing = stride * arm * side if gait_active else 0
            _line(d,[p(side*23,-96+bob),p(side*31+swing,-63+bob),p(side*38+swing,-42+bob)],coat,max(6,int(11*scale)))
            leg = stride * side * (24 if gait_active else 3)
            _line(d,[p(side*17,-35+bob),p(side*22-leg*.55,-16),p(side*25-leg,-1)],coat,max(7,int(13*scale)))
        tail = math.sin(t*4.5)*22
        _line(d,[p(-25,-78+bob),p(-55,-66+tail),p(-70,-91+tail),p(-55,-111+tail)],dark,max(5,int(8*scale)))
    elif species == "turtle":
        bob = math.sin(phase*2)*2.8 if gait_active else 0
        ellipse(-3,-47+bob,58,35,dark,(38,83,58),4)
        ellipse(-3,-50+bob,48,28,(83,132,83),dark,3)
        for dx in (-25,0,20):
            _line(d,[p(dx-9,-66+bob),p(dx+9,-34+bob)],(48,91,62),max(2,int(3*scale)))
        head_extension = 9*action_wave if action in {"reach","push"} else 0
        ellipse(48+head_extension,-59+bob,27,22,coat,dark,3)
        ellipse(63+head_extension,-65+bob,3,4,eye)
        for side in (-1,1):
            for front in (-1,1):
                dx = (35 if front > 0 else -39)+side*9
                swing = math.sin(phase+(0 if front==side else math.pi))*10 if gait_active else 0
                _line(d,[p(dx,-31+bob),p(dx+swing,-12),p(dx+swing+4,-2)],coat,max(7,int(12*scale)))
                ellipse(dx+swing+4,-2,9,5,dark)
    elif species == "bear":
        bob = heavy_bob if gait_active else 0
        ellipse(-2,-63+bob,67,48,coat,dark,4)
        ellipse(42,-111+bob,39,36,coat,dark,3)
        ellipse(18,-143+bob,12,13,coat,dark,2); ellipse(62,-142+bob,12,13,coat,dark,2)
        ellipse(72-lean*.45,-98+bob,21,15,(191,151,119),dark,2)
        ellipse(84-lean*.45,-102+bob,5,4,dark); ellipse(49,-122+bob,4,5,eye)
        for side, offset in ((-1,0.0),(1,math.pi)):
            swing = math.sin(phase+offset)*15 if gait_active else 0
            foot_x = (38 if side==1 else -42) + swing
            shoulder_x = 30 if side==1 else -37
            _line(d,[p(shoulder_x,-45+bob),p(foot_x,-20),p(foot_x,-2)],coat,max(9,int(18*scale)))
            ellipse(foot_x,-1,14,8,dark)
        if action == "push":
            _line(d,[p(50,-95),p(75,-75),p(103,-75)],coat,max(10,int(16*scale)))
    elif species in {"dog","cat"}:
        bob = math.sin(phase*2)*(3 if gait_active else 1)
        ellipse(-2,-47+bob,65,29,coat,dark,3); ellipse(42,-79+bob,28,27,coat,dark,3)
        if species == "dog":
            ellipse(65,-67+bob,23,15,coat,dark,2); ellipse(83,-68+bob,5,4,dark)
            ellipse(35,-105+bob,13,21,dark)
            wag=math.sin(t*8)*12
            _line(d,[p(-60,-47+bob),p(-82,-61+wag),p(-91,-83+wag)],coat,max(6,int(12*scale)))
        else:
            d.polygon([p(24,-97+bob),p(29,-132+bob),p(48,-105+bob)],fill=dark)
            d.polygon([p(49,-103+bob),p(64,-131+bob),p(67,-91+bob)],fill=dark)
            _line(d,[p(55,-47),p(76,-35),p(88,-51),p(79,-69)],dark,max(3,int(7*scale)))
        ellipse(49,-85+bob,4,5,eye)
        for side,offset in ((-1,0),(1,math.pi)):
            swing=math.sin(phase+offset)*21 if gait_active else 0
            hip=30 if side==1 else -35
            _line(d,[p(hip,-38+bob),p(hip+swing*.45,-19+bob),p(hip+swing,-2)],coat,max(7,int(13*scale)))
    elif species == "bird":
        flap=math.sin(t*13)*30 if action in {"fly","jump"} else math.sin(t*2)*4
        bob=math.sin(phase*2)*3 if action=="fly" else 0
        ellipse(0,-48+bob,43,31,coat,dark,3); ellipse(24,-82+bob,25,23,coat,dark,2)
        d.polygon([p(45,-83+bob),p(72,-74+bob),p(47,-66+bob)],fill=(220,157,65))
        ellipse(32,-88+bob,4,5,eye)
        _line(d,[p(-3,-58+bob),p(-28,-75-flap),p(-51,-56-flap)],dark,max(5,int(10*scale)))
        _line(d,[p(2,-54+bob),p(-23,-42+flap),p(-48,-49+flap)],coat,max(5,int(10*scale)))
        for dx in (-12,18): _line(d,[p(dx,-20),p(dx-2,-5),p(dx-10,-1)],(204,151,67),max(3,int(5*scale)))
    elif species == "fish":
        tail=math.sin(t*9)*18
        ellipse(0,-55,64,34,coat,dark,3)
        d.polygon([p(-55,-55),p(-91,-84+tail),p(-88,-25+tail)],fill=dark)
        d.polygon([p(-4,-83),p(20,-111),p(30,-77)],fill=dark)
        ellipse(43,-67,5,6,eye)
    elif species == "elephant":
        bob = math.sin(phase*2) * (2.5 if gait_active else 0.8)
        ellipse(-2,-65+bob,70,48,coat,dark,4)
        ellipse(43,-112+bob,43,39,coat,dark,3)
        ellipse(12,-145+bob,24,30,coat,dark,3)
        ellipse(67,-125+bob,17,25,coat,dark,3)
        # Long curved trunk and two visible tusks.
        _line(d,[p(75,-103+bob),p(91,-78+bob),p(88,-49+bob+lean),p(72,-42+bob+lean)],coat,max(12,int(23*scale)))
        for side in (-1,1):
            _line(d,[p(60+side*7,-91+bob),p(77+side*8,-85+bob)],(238,224,190),max(3,int(6*scale)))
        ellipse(55,-124+bob,4,5,eye)
        for side,offset in ((-1,0),(1,math.pi)):
            swing=math.sin(phase+offset)*10 if gait_active else 0
            _line(d,[p(-35+side*55,-40+bob),p(-35+side*55+swing,-18),p(-35+side*55+swing,-1)],coat,max(10,int(19*scale)))
    elif species == "deer":
        bob=math.sin(phase*2)*(4 if gait_active else 1)
        ellipse(-5,-54+bob,53,29,coat,dark,3)
        ellipse(42,-99+bob,25,34,coat,dark,3)
        _line(d,[p(52,-115+bob),p(65,-139+bob),p(72,-154+bob)],coat,max(7,int(10*scale)))
        _line(d,[p(64,-137+bob),p(50,-151+bob)],coat,max(4,int(6*scale)))
        _line(d,[p(69,-147+bob),p(84,-158+bob)],coat,max(4,int(6*scale)))
        d.polygon([p(29,-119+bob),p(18,-137+bob),p(40,-126+bob)],fill=dark)
        ellipse(56,-108+bob,3,4,eye)
        for side,offset in ((-1,0),(1,math.pi)):
            swing=math.sin(phase+offset)*22 if gait_active else 0
            hip=-32 if side<0 else 27
            _line(d,[p(hip,-38+bob),p(hip+swing*.5,-18),p(hip+swing,-1)],coat,max(6,int(11*scale)))
        for k in range(5):
            ellipse(-35+k*12,-60+bob,2,3,(239,224,195))
    elif species == "fox":
        bob=math.sin(phase*2)*(3 if gait_active else 1)
        ellipse(-4,-50+bob,60,28,coat,dark,3)
        ellipse(43,-86+bob,29,27,coat,dark,3)
        d.polygon([p(25,-103+bob),p(22,-139+bob),p(46,-111+bob)],fill=coat,outline=dark)
        d.polygon([p(52,-107+bob),p(69,-137+bob),p(69,-98+bob)],fill=coat,outline=dark)
        d.polygon([p(61,-82+bob),p(91,-72+bob),p(62,-64+bob)],fill=(224,190,151))
        ellipse(52,-91+bob,3,4,eye)
        tail=math.sin(t*3.5)*7
        _line(d,[p(-48,-52+bob),p(-83,-45+tail),p(-112,-61+tail)],coat,max(15,int(25*scale)))
        ellipse(-111,-61+tail,13,10,(239,226,205),dark,2)
        for side,offset in ((-1,0),(1,math.pi)):
            swing=math.sin(phase+offset)*19 if gait_active else 0
            hip=-30 if side<0 else 27
            _line(d,[p(hip,-34+bob),p(hip+swing*.5,-17),p(hip+swing,-1)],coat,max(6,int(11*scale)))
    elif species == "rabbit":
        bob=math.sin(phase*2)*(5 if gait_active else 1)
        ellipse(-2,-45+bob,43,28,coat,dark,3)
        ellipse(35,-78+bob,25,24,coat,dark,3)
        # Tall ears make the silhouette immediately readable.
        for dx,lean_ear in ((23,-4),(43,5)):
            _line(d,[p(dx,-94+bob),p(dx+lean_ear,-132+bob),p(dx+lean_ear+2,-158+bob)],coat,max(9,int(15*scale)))
            _line(d,[p(dx,-99+bob),p(dx+lean_ear,-132+bob),p(dx+lean_ear+2,-151+bob)],(193,145,145),max(3,int(6*scale)))
        ellipse(47,-82+bob,3,4,eye)
        ellipse(60,-70+bob,5,4,(238,190,184))
        for side,offset in ((-1,0),(1,math.pi)):
            swing=math.sin(phase+offset)*24 if gait_active else 0
            hip=-24 if side<0 else 23
            _line(d,[p(hip,-28+bob),p(hip+swing*.5,-14),p(hip+swing,-1)],coat,max(7,int(12*scale)))
        ellipse(-38,-40+bob,10,10,(245,241,231),dark,2)
    else:  # dinosaur / T-rex
        tail=math.sin(t*2.5)*10
        ellipse(0,-75,55,42,coat,dark,4); ellipse(43,-124,36,27,coat,dark,3)
        d.polygon([p(64,-117),p(103,-108),p(72,-95)],fill=coat,outline=dark)
        ellipse(62,-133,5,5,eye)
        _line(d,[p(-42,-78),p(-78,-67+tail),p(-119,-88+tail)],coat,max(9,int(17*scale)))
        _line(d,[p(25,-96),p(4,-70),p(15,-58)],dark,max(4,int(7*scale)))
        for side in (-1,1):
            swing=math.sin(phase)*side*12 if gait_active else 0
            _line(d,[p(side*22,-46),p(side*25+swing*.5,-22),p(side*27+swing,-1)],coat,max(10,int(19*scale)))
        for i in range(5):
            xx=-25+i*17
            d.polygon([p(xx,-105),p(xx+7,-119),p(xx+14,-101)],fill=dark)

    ellipse(0,2,52 if species not in {"bird","fish"} else 34,5,(4,7,11))
    return True


def available_species() -> tuple[str, ...]:
    return ("human", "monkey", "turtle", "bear", "dog", "cat", "bird", "fish", "dinosaur", "elephant", "deer", "fox", "rabbit")
