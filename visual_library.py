from __future__ import annotations

"""Hash-addressed, local SVG library plus narration-aware animated overlays.

The SVG sprite sheet in assets/visual_library is the editable source of truth.
Each symbol is extracted to its own SHA-256-named SVG in the render output.
Pillow draws the same icon geometry into animated overlays, avoiding a native
SVG rasterizer dependency and keeping the renderer self-contained.
"""
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SVG_PATH = Path(__file__).parent / "assets" / "visual_library" / "psychology_stickers.svg"
NS = "{http://www.w3.org/2000/svg}"
DEFAULT_ASSETS = (
    "brain", "heart", "bird", "bird_cross", "wings", "wings_cross", "airplane",
    "eye", "ear", "lightbulb", "clock", "magnifier", "maze", "puzzle",
    "shield", "target", "question", "check", "cross", "memory", "anxiety",
    "person", "speech", "book", "scale", "lightning", "footprints",
)
PALETTES = {
    "brain": "#D986A0", "heart": "#E96B78", "bird": "#69AEC7",
    "bird_cross": "#69AEC7", "wings": "#9BBFD8", "wings_cross": "#9BBFD8",
    "airplane": "#69AEC7", "eye": "#65A9BF", "ear": "#D69A83",
    "lightbulb": "#E7B94F", "clock": "#7EA8B7", "magnifier": "#79AFC2",
    "maze": "#9A86C4", "puzzle": "#83B58D", "shield": "#76AFC5",
    "target": "#D97B70", "question": "#9882C4", "check": "#7BB58C",
    "cross": "#D45A60", "memory": "#C39A65", "anxiety": "#A58AC5",
    "person": "#79AFC3", "speech": "#79AFC3", "book": "#C39A65",
    "scale": "#7CAFC0", "lightning": "#E5B44C", "footprints": "#7EA6B9",
}
ALIASES = {
    "mind": "brain", "thinking": "brain", "intelligence": "brain",
    "emotion": "heart", "feelings": "heart", "fly": "bird", "flight": "wings",
    "human_brain": "brain", "idea": "lightbulb", "invention": "lightbulb",
    "truth": "magnifier", "evidence": "magnifier", "fact": "check",
    "doubt": "question", "stress": "anxiety", "fear": "anxiety",
    "aircraft": "airplane", "memory_recall": "memory", "prohibition": "bird_cross",
}
ICON_WORDS = (
    (("cannot fly", "can't fly", "cannot_fly", "can't_fly", "unable to fly", "limitation", "limitations"), "bird_cross", "banner", "HUMAN LIMIT"),
    (("intelligent", "intelligence", "brain", "mind", "thinking", "think", "memory", "remember"), "brain", "thought_bubble", "THE HUMAN MIND"),
    (("airplane", "aircraft", "invented", "invention", "technology"), "airplane", "banner", "HUMAN INGENUITY"),
    (("anxiety", "anxious", "fear", "worried", "stress", "overthinking"), "anxiety", "thought_bubble", "EMOTIONAL RESPONSE"),
    (("heart", "emotion", "emotions", "love", "feeling"), "heart", "sticker", "EMOTION"),
    (("see", "vision", "eyes", "watching"), "eye", "sticker", "PERCEPTION"),
    (("hear", "hearing", "sound", "listening"), "ear", "sticker", "SENSORY INPUT"),
    (("time", "clock", "moment", "hours"), "clock", "sticker", "TIME"),
    (("question", "uncertain", "uncertainty", "doubt"), "question", "banner", "UNCERTAINTY"),
    (("proof", "evidence", "fact", "facts", "reality"), "magnifier", "banner", "CHECK THE FACTS"),
    (("idea", "realize", "realized", "insight", "invent"), "lightbulb", "thought_bubble", "AN IDEA"),
    (("protect", "safety", "safe"), "shield", "sticker", "PROTECTION"),
    (("learn", "knowledge", "study", "education"), "book", "sticker", "LEARNING"),
)

def _smooth(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)

def _font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def _extract_symbols() -> dict[str, str]:
    if not SVG_PATH.is_file():
        raise FileNotFoundError(f"Visual library source is missing: {SVG_PATH}")
    root = ET.parse(SVG_PATH).getroot()
    result = {}
    for symbol in root.findall(f".//{NS}symbol"):
        asset_id = symbol.attrib.get("id")
        if not asset_id:
            continue
        view_box = symbol.attrib.get("viewBox", "0 0 128 128")
        body = "".join(ET.tostring(child, encoding="unicode") for child in list(symbol))
        result[asset_id] = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="{view_box}">'
            f'{body}</svg>'
        )
    return result

def materialize_visual_library(output_dir: Path) -> dict[str, str]:
    """Write real SVG assets named by content hash and a small semantic manifest."""
    root = output_dir / "visual-library"
    root.mkdir(parents=True, exist_ok=True)
    symbols = _extract_symbols()
    manifest = {}
    paths = {}
    for asset_id in DEFAULT_ASSETS:
        svg = symbols.get(asset_id)
        if not svg:
            raise ValueError(f"Visual library symbol is missing: {asset_id}")
        digest = hashlib.sha256(svg.encode("utf-8")).hexdigest()
        path = root / f"{digest}.svg"
        if not path.exists():
            path.write_text(svg, encoding="utf-8")
        paths[asset_id] = str(path.resolve())
        manifest[asset_id] = {
            "sha256": digest, "path": str(path.relative_to(output_dir)),
            "media_type": "image/svg+xml", "kind": "sticker",
        }
    (output_dir / "visual-library-manifest.json").write_text(
        json.dumps({"version": 1, "source": "assets/visual_library/psychology_stickers.svg",
                    "assets": manifest}, indent=2), encoding="utf-8")
    return paths

def infer_scene_overlays(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Choose one useful symbolic visual when the planner omitted explicit overlays."""
    text = " ".join(str(scene.get(key, "")) for key in
                    ("narration", "voiceover", "description", "caption", "subcaption")).lower()
    if not text:
        return []
    for terms, asset, visual_type, label in ICON_WORDS:
        if any(term in text for term in terms):
            return [{
                "asset": asset, "visual_type": visual_type, "text": label,
                "start": 0.24, "end": 0.88,
                "position": {"x": 0.73, "y": 0.36},
                "enter": "slide_up", "exit": "slide_left",
                "transition_in": 0.16, "transition_out": 0.16,
            }]
    return []

def prepare_scene_overlays(script: dict[str, Any], output_dir: Path | None = None) -> int:
    total = 0
    for scene in script.get("scenes", []):
        overlays = scene.get("visual_overlays")
        if not isinstance(overlays, list) or not overlays:
            overlays = infer_scene_overlays(scene)
            if overlays:
                scene["visual_overlays"] = overlays
        valid = []
        for overlay in overlays or []:
            if not isinstance(overlay, dict):
                continue
            asset = ALIASES.get(str(overlay.get("asset", "")).lower(),
                                str(overlay.get("asset", "")).lower())
            generated = None
            if asset not in DEFAULT_ASSETS:
                blueprint = overlay.get("visual_design") or overlay.get("drawing_blueprint")
                if not isinstance(blueprint, dict):
                    continue
                from concept_drawer import create_concept_asset
                generated = create_concept_asset(blueprint, output_dir or (Path(__file__).parent / "output"))
                asset = generated["asset"]
            start = max(0.0, min(0.99, float(overlay.get("start", 0.2))))
            end = max(start + 0.01, min(1.0, float(overlay.get("end", 0.88))))
            item = dict(overlay)
            item.update({"asset": asset, "start": start, "end": end})
            if generated:
                item["_generated_preview_path"] = generated["preview_path"]
                item["_generated_svg_path"] = generated["svg_path"]
                item["_generated_sha256"] = generated["sha256"]
            item.setdefault("visual_type", "sticker")
            item.setdefault("enter", "slide_up")
            item.setdefault("exit", "slide_left")
            item.setdefault("transition_in", 0.16)
            item.setdefault("transition_out", 0.16)
            item.setdefault("position", {"x": 0.72, "y": 0.36})
            valid.append(item)
        scene["visual_overlays"] = valid
        total += len(valid)
    return total

def _paint_icon(asset: str, size: int) -> Image.Image:
    """Draw crisp native vector-style icon art; SVG source remains editable in the library."""
    from PIL import ImageDraw
    color = PALETTES.get(asset, "#79AFC3")
    ink = "#40566A"
    icon = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(icon)
    def line(points, fill=ink, width=7):
        d.line(points, fill=fill, width=width, joint="curve")
    def ellipse(box, fill, outline=ink, width=6):
        d.ellipse(box, fill=fill, outline=outline, width=width)
    if asset in ("brain",):
        ellipse((16, 16, 112, 112), "#F3A6A1", ink, 7)
        line((64, 19, 64, 110), "#A84E70", 6)
        for points in [[(20,54),(45,42),(54,62)],[(21,78),(48,67),(55,91)],
                       [(108,52),(85,43),(75,62)],[(106,79),(84,68),(75,91)]]:
            line(points, "#A84E70", 6)
    elif asset == "heart":
        d.polygon([(64,112),(15,63),(16,42),(30,22),(49,23),(64,42),(81,23),(101,22),(114,43),(112,63)],
                  fill="#ED6B79", outline=ink)
        line([(22,64),(45,64),(55,47),(70,83),(81,64),(106,64)], "#FFF4E8", 5)
    elif asset in ("bird", "bird_cross"):
        d.ellipse((15,42,104,100), fill="#72B6CF", outline=ink, width=7)
        d.polygon([(47,58),(85,27),(101,54),(69,80)], fill="#EAF4F2", outline=ink)
        d.polygon([(97,48),(124,60),(98,69)], fill="#F0AC54", outline=ink)
        ellipse((86,37,96,47), "#20394B", None, 0)
        if asset == "bird_cross":
            d.ellipse((6,6,122,122), outline="#D94D52", width=9)
            line([(22,106),(106,22)], "#D94D52", 11)
    elif asset in ("wings", "wings_cross"):
        d.polygon([(63,62),(12,19),(5,35),(32,90),(64,111),(64,80)], fill="#D7E8F4", outline=ink)
        d.polygon([(65,62),(116,19),(123,35),(96,90),(64,111),(64,80)], fill="#D7E8F4", outline=ink)
        line([(64,55),(64,109)], ink, 6)
        if asset == "wings_cross":
            d.ellipse((6,6,122,122), outline="#D94D52", width=9)
            line([(22,106),(106,22)], "#D94D52", 11)
    elif asset == "airplane":
        d.polygon([(8,66),(52,56),(84,11),(98,14),(90,49),(119,59),(119,72),(89,81),(98,108),(84,117),(53,88),(8,78)],
                  fill="#73BBD4", outline=ink)
    elif asset == "eye":
        d.polygon([(7,64),(64,18),(121,64),(64,110)], fill="#F7F6EF", outline=ink)
        ellipse((38,38,90,90), "#73B7CC", ink, 6); ellipse((53,53,75,75), "#243A50", None, 0)
        ellipse((52,49,62,59), "#FFFFFF", None, 0)
    elif asset == "ear":
        d.arc((22,8,112,119), 180, 500, fill="#704D51", width=12)
        d.arc((39,30,93,104), 190, 510, fill="#AD6D70", width=9)
    elif asset == "lightbulb":
        ellipse((26,10,102,91), "#FFD66E", ink, 7)
        line([(43,89),(43,105),(85,105),(85,89)], ink, 7)
        line([(51,116),(77,116)], ink, 7)
        line([(64,25),(64,59)], "#FFF5CE", 6)
    elif asset == "clock":
        ellipse((10,10,118,118), "#F8F5E9", ink, 8)
        line([(64,25),(64,66),(94,85)], ink, 9)
    elif asset == "magnifier":
        ellipse((16,12,86,82), "#D9EEF2", ink, 9)
        line([(75,75),(116,116)], ink, 14)
        line([(32,48),(47,32),(61,31)], "#FFFFFF", 5)
    elif asset == "maze":
        d.rounded_rectangle((10,10,118,118), 12, fill="#E6DFF5", outline=ink, width=7)
        line([(31,29),(31,58),(62,58),(62,29),(92,29),(92,55),(76,55),(76,87),(98,87),(98,102),(50,102),(50,78),(30,78)], "#856EB1", 8)
    elif asset == "puzzle":
        d.rounded_rectangle((15,15,113,113), 14, fill="#A6CFAE", outline=ink, width=7)
        d.ellipse((47,4,78,35), fill="#A6CFAE", outline=ink, width=5)
        d.rectangle((49,62,80,83), fill="#F6F3DD")
    elif asset == "shield":
        d.polygon([(64,8),(110,26),(105,74),(64,119),(23,74),(18,26)], fill="#91C4D9", outline=ink)
        line([(39,63),(57,81),(91,43)], "#FFFFFF", 10)
    elif asset == "target":
        ellipse((10,10,118,118), "#F8F3E9", "#D36E65", 8)
        ellipse((30,30,98,98), "#F2B5A5", "#D36E65", 7)
        ellipse((50,50,78,78), "#D36E65", None, 0)
    elif asset == "question":
        line([(39,45),(42,31),(57,21),(81,25),(94,42),(86,57),(68,68),(66,86)], "#8C78B7", 14)
        ellipse((58,102,74,118), "#E7A15D", None, 0)
    elif asset == "check":
        ellipse((9,9,119,119), "#A9D7B2", "#416E51", 8)
        line([(33,66),(54,86),(98,38)], "#FFFFFF", 12)
    elif asset == "cross":
        ellipse((9,9,119,119), "#F8E9E3", "#B94D50", 8)
        line([(41,41),(87,87)], "#D44F55", 13); line([(87,41),(41,87)], "#D44F55", 13)
    elif asset == "memory":
        d.rounded_rectangle((18,22,110,106), 8, fill="#E9D9AE", outline="#806A4C", width=7)
        for y in (45,65,85): line([(35,y),(91,y)], "#B58D61", 6)
    elif asset == "anxiety":
        points=[]
        for i in range(20):
            radius=55 if i%2==0 else 38
            angle=-math.pi/2+i*math.pi/10
            points.append((64+math.cos(angle)*radius,64+math.sin(angle)*radius))
        d.polygon(points, fill="#D6C1E8", outline="#665477")
        line([(42,51),(50,46)], "#665477", 6); line([(78,46),(86,51)], "#665477", 6)
        d.arc((43,62,85,95), 195, 345, fill="#665477", width=6)
    elif asset == "person":
        ellipse((46,8,82,44), "#E9B28F", "#64505A", 6)
        d.rounded_rectangle((29,45,99,113), 25, fill="#79AFC3", outline=ink, width=7)
    elif asset == "speech":
        d.rounded_rectangle((10,15,118,93), 15, fill="#F8F4E9", outline=ink, width=7)
        d.polygon([(28,89),(25,115),(55,89)], fill="#F8F4E9", outline=ink)
        for x in (42,64,86): ellipse((x-4,51,x+4,59), "#6BAFC4", None, 0)
    elif asset == "book":
        d.polygon([(10,25),(62,38),(64,110),(10,98)], fill="#EBCB8D", outline="#745B45")
        d.polygon([(64,38),(118,25),(118,98),(64,110)], fill="#EBCB8D", outline="#745B45")
        line([(64,38),(64,110)], "#745B45", 6)
    elif asset == "scale":
        line([(64,12),(64,110),(36,110),(94,110)], ink, 8); line([(22,39),(106,39),(64,12)], ink, 7)
        d.polygon([(7,43),(37,43),(22,75)], fill="#9BC5D4", outline=ink)
        d.polygon([(91,43),(121,43),(106,75)], fill="#9BC5D4", outline=ink)
    elif asset == "lightning":
        d.polygon([(70,5),(22,72),(55,72),(48,123),(107,50),(75,50)], fill="#FFD36B", outline="#7B653E")
    elif asset == "footprints":
        d.ellipse((18,48,58,111), fill="#A9C5D1", outline=ink, width=6)
        d.ellipse((68,12,108,76), fill="#A9C5D1", outline=ink, width=6)
        for box in [(9,26,21,38),(25,17,37,29),(42,24,54,36),(61,2,73,14),(78,0,90,12),(97,8,109,20)]:
            ellipse(box, "#A9C5D1", None, 0)
    return icon.resize((size, size), Image.Resampling.LANCZOS)

def _overlay_icon(spec: dict[str, Any], asset: str, size: int) -> Image.Image:
    custom = spec.get("_generated_preview_path")
    if custom and Path(custom).is_file():
        return Image.open(custom).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    return _paint_icon(asset, size)


def _overlay_card(spec: dict[str, Any]) -> Image.Image:
    kind = str(spec.get("visual_type", "sticker")).lower()
    asset = str(spec.get("asset", "question"))
    text = str(spec.get("text") or spec.get("label") or "").strip().upper()
    if kind == "thought_bubble":
        width, height = 450, 230
    elif kind == "banner":
        width, height = 560, 154
    else:
        width, height = 250, 220
    card = Image.new("RGBA", (width, height), (0,0,0,0))
    shadow = Image.new("RGBA", (width, height), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    if kind == "thought_bubble":
        sd.rounded_rectangle((41,22,width-21,height-45), 55, fill=(8,18,28,80))
    elif kind == "banner":
        sd.rounded_rectangle((10,18,width-10,height-18), 38, fill=(8,18,28,78))
    else:
        sd.ellipse((18,7,width-18,height-7), fill=(8,18,28,75))
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(card)
    accent = PALETTES.get(asset, "#79AFC3")
    if kind == "thought_bubble":
        d.rounded_rectangle((32,12,width-30,height-55), 48, fill="#FFFDF7", outline="#304A60", width=6)
        d.ellipse((65,height-72,112,height-26), fill="#FFFDF7", outline="#304A60", width=5)
        d.ellipse((33,height-39,62,height-10), fill="#FFFDF7", outline="#304A60", width=4)
        icon = _overlay_icon(spec, asset, 112)
        card.alpha_composite(icon, (65,51))
        if text:
            d.text((196,90), text[:19], font=_font(19, True), fill="#344B60")
            d.rounded_rectangle((196,124,390,132), 4, fill=accent)
    elif kind == "banner":
        d.polygon([(0,35),(65,35),(36,75),(65,119),(0,119)], fill=accent)
        d.polygon([(width-65,35),(width,35),(width,height-35),(width-65,height-35),(width-34,height//2)], fill=accent)
        d.rounded_rectangle((34,16,width-34,height-16), 32, fill="#FFFDF7", outline="#304A60", width=5)
        icon = _overlay_icon(spec, asset, 104)
        card.alpha_composite(icon, (53,25))
        if text:
            d.text((178,55), text[:29], font=_font(22, True), fill="#344B60")
            d.text((180,88), "A VISUAL EXPLANATION", font=_font(12, True), fill=accent)
    else:
        d.ellipse((15,5,width-15,height-5), fill="#FFFDF7", outline="#304A60", width=6)
        icon = _paint_icon(asset, 112)
        card.alpha_composite(icon, ((width-112)//2,27))
        if text:
            d.rounded_rectangle((30,height-53,width-30,height-20), 14, fill=accent)
            f = _font(13, True)
            box = d.textbbox((0,0), text[:21], font=f)
            d.text(((width-(box[2]-box[0]))//2,height-47), text[:21], font=f, fill="#FFFFFF")
    return card

def _move_for(kind: str, amount: float, dx: int, dy: int) -> tuple[int, int]:
    amount = _smooth(amount)
    if kind == "slide_up": return (0, int(dy * (1-amount)))
    if kind == "slide_down": return (0, int(-dy * (1-amount)))
    if kind == "slide_left": return (int(dx * (1-amount)), 0)
    if kind == "slide_right": return (int(-dx * (1-amount)), 0)
    return (0, 0)

def render_visual_overlays(image: Image.Image, scene: dict[str, Any], progress: float,
                           library_paths: dict[str, str] | None = None) -> Image.Image:
    overlays = scene.get("visual_overlays") or []
    if not overlays:
        return image
    result = image.convert("RGBA")
    width, height = result.size
    for spec in overlays:
        if not isinstance(spec, dict):
            continue
        asset = str(spec.get("asset", "question"))
        custom_preview = spec.get("_generated_preview_path")
        if library_paths is not None and asset not in library_paths and not (custom_preview and Path(custom_preview).is_file()):
            continue
        start, end = float(spec.get("start", 0.2)), float(spec.get("end", 0.88))
        if progress < start or progress > end:
            continue
        window = max(0.05, end-start)
        in_duration = max(0.04, float(spec.get("transition_in", 0.16)))
        out_duration = max(0.04, float(spec.get("transition_out", 0.16)))
        enter_amount = _smooth((progress-start)/in_duration)
        exit_amount = _smooth((end-progress)/out_duration)
        alpha = min(enter_amount, exit_amount)
        if alpha <= 0.005:
            continue
        card = _overlay_card(spec)
        enter_kind = str(spec.get("enter", "slide_up"))
        exit_kind = str(spec.get("exit", "slide_left"))
        ex, ey = _move_for(enter_kind, enter_amount, 105, 85)
        xx, xy = _move_for(exit_kind, exit_amount, 105, 85)
        px, py = ex-xx, ey-xy
        scale = 0.92 + 0.08 * enter_amount
        scale *= 0.96 + 0.04 * exit_amount
        if enter_kind in ("draw_on", "reveal"):
            scale *= 0.96 + 0.04 * enter_amount
        if abs(scale-1.0) > 0.001:
            card = card.resize((max(1,int(card.width*scale)), max(1,int(card.height*scale))), Image.Resampling.LANCZOS)
        card.putalpha(card.getchannel("A").point(lambda value: int(value*alpha)))
        position = spec.get("position") or {}
        if isinstance(position, (list, tuple)) and len(position) == 2:
            nx, ny = float(position[0]), float(position[1])
        elif isinstance(position, dict):
            nx, ny = float(position.get("x", 0.72)), float(position.get("y", 0.36))
        else:
            nx, ny = 0.72, 0.36
        cx, cy = int(nx*width+px), int(ny*height+py)
        result.alpha_composite(card, (cx-card.width//2, cy-card.height//2))
    return result.convert("RGB")
