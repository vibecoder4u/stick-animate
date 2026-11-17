from __future__ import annotations

"""Self-contained, AI-directed artwork compiler for Stick Animate.

The visual designer supplies a semantic design brief (and may supply a structured
visual_design object). This module turns that brief into editable SVG plus
transparent component layers and a preview PNG. It uses only Pillow and the
Python standard library: no image API, network request, stock image, or external
asset service is involved.
"""
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
PALETTES = {
    "warm": ((224, 145, 74), (247, 205, 137), (91, 55, 43), (246, 224, 184)),
    "cool": ((76, 153, 190), (151, 211, 224), (37, 77, 104), (222, 241, 245)),
    "forest": ((105, 151, 83), (181, 205, 119), (55, 83, 48), (238, 224, 177)),
    "royal": ((124, 105, 185), (190, 163, 222), (58, 48, 92), (244, 226, 185)),
    "neutral": ((153, 153, 151), (211, 205, 190), (67, 67, 70), (242, 234, 215)),
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:64] or "asset"


def _pick_design(request: dict[str, Any]) -> dict[str, Any]:
    """Normalize a designer brief into a safe, renderer-friendly design schema."""
    supplied = request.get("visual_design") or request.get("design") or {}
    if not isinstance(supplied, dict):
        supplied = {}
    name = str(request.get("name") or "original asset")
    brief = " ".join(str(request.get(k, "")) for k in ("prompt", "visual_description", "description")).lower()
    identity = name.lower() + " " + brief
    archetype = str(supplied.get("anatomy") or supplied.get("archetype") or "")
    if not archetype:
        if any(word in identity for word in ("penguin", "bird", "eagle", "owl", "parrot", "phoenix")):
            archetype = "bird"
        elif any(word in identity for word in ("fish", "shark", "whale", "dolphin", "mermaid")):
            archetype = "fish"
        elif any(word in identity for word in ("snake", "serpent", "worm", "eel")):
            archetype = "serpentine"
        elif any(word in identity for word in ("spider", "insect", "ant", "beetle", "robot", "alien")):
            archetype = "multi_limb"
        elif any(word in identity for word in ("horse", "deer", "fox", "wolf", "dog", "cat", "tiger", "lion", "bear", "cow", "elephant")):
            archetype = "quadruped"
        else:
            archetype = "biped"
    palette_name = str(supplied.get("palette") or
                       ("cool" if any(w in identity for w in ("ice", "snow", "penguin", "ocean")) else
                        "forest" if any(w in identity for w in ("forest", "leaf", "frog", "turtle")) else
                        "royal" if any(w in identity for w in ("magic", "dragon", "phoenix")) else "warm"))
    palette = PALETTES.get(palette_name, PALETTES["warm"])
    colors = supplied.get("colors") if isinstance(supplied.get("colors"), dict) else {}
    body = str(colors.get("body") or supplied.get("body_color") or "#%02x%02x%02x" % palette[0])
    accent = str(colors.get("accent") or supplied.get("accent_color") or "#%02x%02x%02x" % palette[1])
    outline = str(colors.get("outline") or supplied.get("outline_color") or "#%02x%02x%02x" % palette[2])
    belly = str(colors.get("belly") or supplied.get("belly_color") or "#%02x%02x%02x" % palette[3])
    return {
        "schema_version": 1, "name": name, "kind": str(request.get("kind") or "prop"),
        "anatomy": archetype, "palette": palette_name,
        "colors": {"body": body, "accent": accent, "outline": outline, "belly": belly},
        "silhouette": str(supplied.get("silhouette") or archetype),
        "distinctive_features": list(supplied.get("distinctive_features") or []),
        "description": str(supplied.get("description") or request.get("prompt") or name),
        "style": str(supplied.get("style") or "polished colorful 2D cartoon, expressive silhouette, clean ink outline, soft cel shading"),
        "parts": supplied.get("parts") if isinstance(supplied.get("parts"), list) else [],
    }


def _rgb(color: str, fallback=(150, 150, 150)) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    try:
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return fallback


def _svg_for_design(design: dict[str, Any]) -> str:
    c = design["colors"]
    title = escape(design["name"])
    anatomy = design["anatomy"]
    # The SVG is deliberately componentized so later rigging can address parts.
    if design["kind"] == "character":
        if anatomy == "bird":
            body = '<ellipse cx="250" cy="295" rx="105" ry="128"/><path d="M320 275 Q410 210 420 310 Q365 360 310 345Z" fill="{accent}"/><path d="M330 190 Q365 90 390 190 Q365 220 330 190Z" fill="{accent}"/>'.format(accent=c["accent"])
            head = '<circle cx="250" cy="145" r="78"/><path d="M315 145 L405 175 L315 198Z" fill="{belly}"/>'.format(belly=c["belly"])
            limbs = '<path d="M215 405 L205 460 M280 405 L290 460" stroke="{outline}" stroke-width="18" stroke-linecap="round"/><path d="M190 460 L155 475 M290 460 L325 475" stroke="{accent}" stroke-width="16" stroke-linecap="round"/>'.format(outline=c["outline"],accent=c["accent"])
        elif anatomy == "fish":
            body = '<path d="M105 290 Q190 145 350 235 Q410 290 350 345 Q190 435 105 290Z"/><path d="M350 285 L455 205 L445 370Z" fill="{accent}"/>'.format(accent=c["accent"])
            head = '<circle cx="195" cy="265" r="12" fill="{outline}"/>'.format(outline=c["outline"])
            limbs = '<path d="M235 300 Q280 360 325 300" fill="none" stroke="{belly}" stroke-width="18"/>'.format(belly=c["belly"])
        elif anatomy == "serpentine":
            body = '<path d="M85 365 C120 160 260 420 300 230 S410 145 430 285" fill="none" stroke="{body}" stroke-width="76" stroke-linecap="round"/>'.format(body=c["body"])
            head = '<ellipse cx="430" cy="285" rx="60" ry="43"/>'
            limbs = ""
        elif anatomy == "quadruped":
            body = '<ellipse cx="250" cy="295" rx="145" ry="90"/><path d="M345 270 Q405 190 430 245 L415 325 Q365 350 340 320Z" fill="{accent}"/>'.format(accent=c["accent"])
            head = '<ellipse cx="405" cy="205" rx="65" ry="62"/><path d="M370 155 L355 95 L400 145Z" fill="{accent}"/><path d="M420 155 L455 105 L455 180Z" fill="{accent}"/>'.format(accent=c["accent"])
            limbs = '<path d="M155 345 L145 445 M220 350 L220 448 M320 345 L330 445 M375 330 L390 430" stroke="{outline}" stroke-width="28" stroke-linecap="round"/>'.format(outline=c["outline"])
        else:
            body = '<path d="M175 210 Q250 170 325 210 L350 390 Q250 440 150 390Z"/>'
            head = '<circle cx="250" cy="135" r="78"/>'
            limbs = '<path d="M175 245 L100 350 M325 245 L400 350 M205 385 L185 475 M295 385 L315 475" stroke="{outline}" stroke-width="28" stroke-linecap="round"/>'.format(outline=c["outline"])
        face = '<ellipse cx="278" cy="145" rx="10" ry="14" fill="{outline}"/><ellipse cx="322" cy="145" rx="10" ry="14" fill="{outline}"/><path d="M285 180 Q305 195 325 180" fill="none" stroke="{outline}" stroke-width="8" stroke-linecap="round"/>'.format(outline=c["outline"])
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<title>{title}</title><desc>{escape(design["description"])}</desc>
<g id="limbs" fill="{c["body"]}" stroke="{c["outline"]}" stroke-width="12" stroke-linejoin="round">{limbs}</g>
<g id="body" fill="{c["body"]}" stroke="{c["outline"]}" stroke-width="12" stroke-linejoin="round">{body}</g>
<g id="head" fill="{c["body"]}" stroke="{c["outline"]}" stroke-width="12" stroke-linejoin="round">{head}</g>
<g id="face">{face}</g><g id="highlights"><ellipse cx="215" cy="260" rx="48" ry="22" fill="{c["belly"]}" opacity=".72"/></g></svg>'''
    if design["kind"] == "background":
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<title>{title}</title><defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#8cc8e8"/><stop offset="1" stop-color="#f5d7a0"/></linearGradient></defs>
<g id="sky"><rect width="1280" height="720" fill="url(#sky)"/></g>
<g id="distant"><path d="M0 470 L230 210 430 455 680 170 920 465 1110 250 1280 450V720H0Z" fill="{c["accent"]}"/></g>
<g id="ground"><path d="M0 525 Q350 450 680 535 T1280 510V720H0Z" fill="{c["body"]}"/></g></svg>'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<title>{title}</title><desc>{escape(design["description"])}</desc>
<g id="shadow" fill="#18202a" opacity=".18"><ellipse cx="256" cy="440" rx="175" ry="28"/></g>
<g id="object" fill="{c["body"]}" stroke="{c["outline"]}" stroke-width="14" stroke-linejoin="round">
<path d="M95 335 Q110 245 180 225 L185 125 Q256 85 327 125 L330 225 Q400 250 417 335 L385 400 Q256 445 127 400Z"/>
</g><g id="details" fill="{c["accent"]}"><path d="M190 145 Q256 110 322 145 L315 210 Q256 235 197 210Z"/><circle cx="210" cy="310" r="15"/><circle cx="300" cy="310" r="15"/></g></svg>'''


def _draw_character_layers(design: dict[str, Any], folder: Path) -> Image.Image:
    c = design["colors"]
    body, accent, outline, belly = (_rgb(c[k]) for k in ("body", "accent", "outline", "belly"))
    anatomy = design["anatomy"]
    layers: dict[str, Image.Image] = {}
    def layer(name: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        layers[name] = im
        return im, ImageDraw.Draw(im)
    im, d = layer("rear-limbs")
    if anatomy in ("bird", "biped", "multi_limb"):
        d.line((220, 360, 200, 465), fill=outline, width=28)
        d.line((292, 360, 310, 465), fill=outline, width=28)
        d.line((200, 465, 160, 475), fill=accent, width=18)
        d.line((310, 465, 350, 475), fill=accent, width=18)
    elif anatomy == "quadruped":
        for x in (155, 220, 315, 375):
            d.line((x, 330, x + (x%2)*10, 465), fill=outline, width=30)
            d.ellipse((x-22, 445, x+28, 480), fill=accent, outline=outline, width=7)
    elif anatomy == "fish":
        d.polygon([(345, 255), (465, 165), (455, 365)], fill=accent, outline=outline)
        d.arc((210, 245, 340, 380), 5, 170, fill=belly, width=20)
    elif anatomy == "serpentine":
        d.line([(80,390),(145,300),(220,365),(300,260),(390,230)], fill=body, width=82, joint="curve")
        d.line([(80,365),(145,275),(220,340),(300,235),(390,205)], fill=accent, width=12, joint="curve")
    else:
        for i in range(6):
            angle = i * math.pi / 3
            sx, sy = 250 + math.cos(angle)*65, 295 + math.sin(angle)*55
            ex, ey = 250 + math.cos(angle)*170, 295 + math.sin(angle)*150
            d.line((sx, sy, ex, ey), fill=outline, width=17)
            d.ellipse((ex-12, ey-12, ex+12, ey+12), fill=accent, outline=outline, width=4)
    im, d = layer("body")
    if anatomy == "bird":
        d.ellipse((145, 185, 360, 430), fill=body, outline=outline, width=12)
        d.ellipse((245, 245, 410, 365), fill=accent, outline=outline, width=8)
        d.ellipse((195, 300, 320, 405), fill=belly)
    elif anatomy == "fish":
        d.ellipse((90, 160, 390, 420), fill=body, outline=outline, width=12)
        d.polygon([(350, 290), (475, 190), (465, 400)], fill=accent, outline=outline)
    elif anatomy == "serpentine":
        d.line([(75,390),(145,300),(220,365),(300,260),(390,230)], fill=body, width=82, joint="curve")
    elif anatomy == "quadruped":
        d.ellipse((90, 190, 405, 385), fill=body, outline=outline, width=12)
        d.ellipse((245, 235, 385, 365), fill=belly)
        d.arc((80, 160, 240, 390), 190, 310, fill=accent, width=16)
    else:
        d.rounded_rectangle((160, 185, 345, 410), radius=78, fill=body, outline=outline, width=12)
        d.ellipse((190, 265, 315, 385), fill=belly)
    im, d = layer("head")
    if anatomy == "bird":
        d.ellipse((185, 70, 335, 235), fill=body, outline=outline, width=12)
        d.polygon([(315, 145), (430, 175), (320, 200)], fill=accent, outline=outline)
        d.polygon([(215, 92), (205, 20), (260, 85)], fill=accent, outline=outline)
    elif anatomy == "fish":
        d.ellipse((110, 190, 280, 360), fill=body, outline=outline, width=10)
    elif anatomy == "serpentine":
        d.ellipse((345, 165, 475, 280), fill=body, outline=outline, width=10)
        d.polygon([(435, 215), (490, 240), (435, 255)], fill=accent, outline=outline)
    elif anatomy == "quadruped":
        d.ellipse((320, 115, 465, 270), fill=body, outline=outline, width=12)
        d.polygon([(345, 145), (330, 65), (395, 125)], fill=accent, outline=outline)
        d.polygon([(420, 145), (470, 75), (465, 180)], fill=accent, outline=outline)
    else:
        d.ellipse((175, 55, 345, 230), fill=body, outline=outline, width=12)
        d.ellipse((185, 40, 255, 125), fill=accent, outline=outline, width=7)
        d.ellipse((270, 40, 340, 125), fill=accent, outline=outline, width=7)
    im, d = layer("face")
    if anatomy != "fish":
        d.ellipse((255, 130, 273, 155), fill=outline)
        d.ellipse((305, 130, 323, 155), fill=outline)
        d.arc((265, 150, 325, 200), 5, 160, fill=outline, width=7)
    else:
        d.ellipse((205, 245, 230, 270), fill=outline)
        d.ellipse((212, 250, 220, 258), fill=(255,255,255))
    # Save independent transparent layers and composite in deterministic order.
    folder.mkdir(parents=True, exist_ok=True)
    composite = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for name, image in layers.items():
        image.save(folder / f"{name}.png")
        composite.alpha_composite(image)
    return composite


def _draw_prop(design: dict[str, Any]) -> Image.Image:
    c = design["colors"]
    body, accent, outline, belly = (_rgb(c[k]) for k in ("body", "accent", "outline", "belly"))
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    name = design["name"].lower()
    d.ellipse((65, 420, 450, 475), fill=(15, 20, 25, 45))
    if any(w in name for w in ("car", "motorcycle", "bike", "vehicle", "truck")):
        d.rounded_rectangle((70, 235, 445, 385), radius=45, fill=body, outline=outline, width=14)
        d.polygon([(145,235),(195,145),(330,145),(390,235)], fill=accent, outline=outline)
        for x in (155, 365):
            d.ellipse((105+x-80, 340, 105+x-20, 440), fill=(40,45,50), outline=outline, width=9)
            d.ellipse((105+x-64, 356, 105+x-36, 412), fill=belly)
    elif any(w in name for w in ("tree", "log", "branch")):
        d.rounded_rectangle((45, 215, 465, 325), radius=48, fill=body, outline=outline, width=14)
        d.ellipse((35, 215, 125, 325), fill=accent, outline=outline, width=10)
        for x in (200, 280, 360):
            d.arc((x-30, 230, x+35, 310), 180, 360, fill=belly, width=7)
    elif any(w in name for w in ("ball", "apple", "fruit", "planet", "stone", "rock")):
        d.ellipse((100, 95, 410, 405), fill=body, outline=outline, width=14)
        d.ellipse((160, 145, 240, 225), fill=belly)
        d.line((255, 100, 270, 55), fill=outline, width=12)
        d.ellipse((260, 45, 330, 85), fill=accent)
    elif any(w in name for w in ("compass", "clock", "wheel", "coin", "shield")):
        d.ellipse((90, 90, 420, 420), fill=body, outline=outline, width=18)
        d.ellipse((145, 145, 365, 365), outline=accent, width=15)
        d.polygon([(255,165),(290,275),(255,245),(220,275)], fill=belly, outline=outline)
    else:
        d.rounded_rectangle((100, 105, 410, 420), radius=48, fill=body, outline=outline, width=14)
        d.rounded_rectangle((135, 145, 375, 210), radius=20, fill=accent)
        d.ellipse((210, 260, 300, 350), fill=belly, outline=outline, width=8)
    return image


def create_native_asset(request: dict[str, Any], output_dir: Path) -> dict[str, str]:
    """Compile a design brief to SVG, layered PNGs, preview PNG and metadata."""
    design = _pick_design(request)
    asset_id = _slug(str(request.get("asset_id") or design["name"]))
    folder = output_dir / asset_id
    folder.mkdir(parents=True, exist_ok=True)
    if design["kind"] == "character":
        preview = _draw_character_layers(design, folder / "layers")
    elif design["kind"] == "background":
        preview = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        d = ImageDraw.Draw(preview)
        d.rectangle((0, 0, 1280, 430), fill=(140, 202, 232))
        d.ellipse((930, 70, 1100, 240), fill=(255, 224, 155))
        d.polygon([(0, 500),(220,220),(430,480),(670,180),(920,490),(1110,250),(1280,480),(1280,720),(0,720)], fill=_rgb(design["colors"]["accent"]))
        d.rectangle((0, 525, 1280, 720), fill=_rgb(design["colors"]["body"]))
        preview.save(folder / "layers" / "environment.png")
    else:
        preview = _draw_prop(design)
        (folder / "layers").mkdir(parents=True, exist_ok=True)
        preview.save(folder / "layers" / "object.png")
    svg = _svg_for_design(design)
    svg_path = folder / "artwork.svg"
    svg_path.write_text(svg, encoding="utf-8")
    preview_path = folder / "preview.png"
    preview.save(preview_path)
    metadata = {
        "asset_id": asset_id, "name": design["name"], "kind": design["kind"],
        "design": design, "format": "layered-svg-png", "renderer": "native-artwork-v1",
        "files": {"svg": str(svg_path.resolve()), "preview": str(preview_path.resolve()),
                  "layers": str((folder / "layers").resolve())},
        "content_hash": hashlib.sha256(json.dumps(design, sort_keys=True).encode()).hexdigest(),
    }
    metadata_path = folder / "asset.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"asset_id": asset_id, "path": str(preview_path.resolve()),
            "svg_path": str(svg_path.resolve()), "metadata_path": str(metadata_path.resolve()),
            "layers_path": str((folder / "layers").resolve())}


def draw_native_character(image: Image.Image, actor: dict[str, Any],
                          pose: dict[str, Any], t: float) -> bool:
    """Draw an unfamiliar species using a generated anatomy archetype, never a human fallback."""
    request = {
        "name": actor.get("name") or actor.get("species") or "original creature",
        "kind": "character", "prompt": actor.get("visual_description", ""),
        "visual_design": actor.get("visual_design") or actor.get("design") or {},
    }
    design = _pick_design(request)
    c = design["colors"]
    body, accent, outline, belly = (_rgb(c[k]) for k in ("body", "accent", "outline", "belly"))
    x, y = float(pose.get("x", 640)), float(pose.get("y", 610))
    scale = max(.2, min(3.0, float(actor.get("scale", 1.0))))
    phase = float(pose.get("gait_phase", t * 6.0))
    action = str(pose.get("pose", "idle")).lower()
    moving = action in {"walk", "run", "jump", "fly", "swim"}
    bob = math.sin(phase * 2) * (5 if moving else 1.5)
    jump = 26 * max(0.0, math.sin(math.pi * float(pose.get("action_progress", 0.5)))) if action == "jump" else 0
    y -= bob + jump
    layer = Image.new("RGBA", image.size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    def box(a,b,cx,dy):
        return tuple(int(v) for v in (x+a*scale, y+b*scale, x+cx*scale, y+dy*scale))
    if design["anatomy"] == "bird":
        d.ellipse(box(-40,-105,42,-18), fill=body, outline=outline, width=max(2,int(4*scale)))
        d.ellipse(box(-30,-165,35,-105), fill=body, outline=outline, width=max(2,int(4*scale)))
        d.polygon([(x+28*scale,y-143*scale),(x+78*scale,y-130*scale),(x+28*scale,y-118*scale)], fill=accent, outline=outline)
        d.polygon([(x-20*scale,y-85*scale),(x+20*scale,y-85*scale),(x+45*scale,y-45*scale),(x-35*scale,y-45*scale)], fill=accent, outline=outline)
        for dx in (-18,18):
            d.line((x+dx*scale,y-20*scale,x+dx*scale,y+5*scale), fill=outline, width=max(2,int(5*scale)))
    elif design["anatomy"] == "fish":
        d.ellipse(box(-62,-112,55,-18), fill=body, outline=outline, width=max(2,int(4*scale)))
        d.polygon([(x+48*scale,y-68*scale),(x+95*scale,y-108*scale),(x+95*scale,y-28*scale)], fill=accent, outline=outline)
        d.ellipse(box(16,-92,24,-84), fill=outline)
    elif design["anatomy"] == "serpentine":
        points=[(x-90*scale,y-15*scale),(x-55*scale,y-55*scale),(x-15*scale,y-18*scale),(x+28*scale,y-72*scale),(x+72*scale,y-58*scale)]
        d.line(points, fill=body, width=max(8,int(24*scale)), joint="curve")
        d.ellipse(box(52,-85,100,-40), fill=body, outline=outline, width=max(2,int(4*scale)))
    elif design["anatomy"] == "quadruped":
        d.ellipse(box(-68,-105,48,-22), fill=body, outline=outline, width=max(2,int(4*scale)))
        d.ellipse(box(28,-142,92,-75), fill=body, outline=outline, width=max(2,int(4*scale)))
        d.polygon([(x+40*scale,y-126*scale),(x+35*scale,y-170*scale),(x+62*scale,y-132*scale)], fill=accent, outline=outline)
        swing=math.sin(phase)*15 if moving else 2
        for dx in (-42,-12,25,55):
            d.line((x+dx*scale,y-40*scale,x+(dx+swing)*scale,y+2*scale), fill=outline, width=max(5,int(12*scale)))
        d.ellipse(box(-28,-55,20,-25), fill=belly)
    else:
        d.rounded_rectangle(box(-42,-120,42,-15), radius=max(8,int(24*scale)), fill=body, outline=outline, width=max(2,int(4*scale)))
        d.ellipse(box(-38,-178,38,-100), fill=body, outline=outline, width=max(2,int(4*scale)))
        swing=math.sin(phase)*18 if moving else 2
        for dx, sign in ((-22,-1),(22,1)):
            d.line((x+dx*scale,y-35*scale,x+(dx+swing*sign)*scale,y+5*scale), fill=outline, width=max(5,int(13*scale)))
            d.line((x+dx*scale,y-105*scale,x+(dx-12*sign)*scale,y-65*scale), fill=outline, width=max(4,int(10*scale)))
    # Shared expression and specular accents; actor-level colors remain stable between scenes.
    if design["anatomy"] not in ("fish","serpentine"):
        d.ellipse(box(8,-160,16,-150), fill=outline)
        d.ellipse(box(25,-160,33,-150), fill=outline)
        d.arc(box(8,-145,34,-126), 0, 160, fill=outline, width=max(1,int(2*scale)))
    image.alpha_composite(layer)
    return True
