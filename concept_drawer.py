from __future__ import annotations

"""Safe, local concept-to-SVG drawing compiler.

The AI supplies a small declarative vector blueprint; this module validates it,
writes editable SVG, and creates a Pillow preview for the existing overlay renderer.
It does not call an image API or execute model-provided code.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ALLOWED = {"circle", "ellipse", "rect", "round_rect", "line", "polygon", "polyline", "text"}
MAX_ELEMENTS = 48

def _num(value: Any, default: float = 0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return max(-256.0, min(384.0, result))

def _color(value: Any, default: str = "#79AFC3") -> str:
    value = str(value or default)
    return value if HEX.fullmatch(value) else default

def _points(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 2 or len(value) > 64:
        raise ValueError("Vector points must contain 2..64 coordinate pairs")
    result = []
    for pair in value:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("Each point must be an [x, y] pair")
        result.append((_num(pair[0]), _num(pair[1])))
    return result

def validate_blueprint(blueprint: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        raise ValueError("visual_design must be an object")
    elements = blueprint.get("elements")
    if not isinstance(elements, list) or not elements or len(elements) > MAX_ELEMENTS:
        raise ValueError(f"visual_design.elements must contain 1..{MAX_ELEMENTS} shapes")
    clean = []
    for raw in elements:
        if not isinstance(raw, dict) or raw.get("type") not in ALLOWED:
            raise ValueError("Unsupported vector element")
        item = dict(raw)
        item["type"] = raw["type"]
        item["fill"] = _color(raw.get("fill"), "none") if raw.get("fill") != "none" else "none"
        item["stroke"] = _color(raw.get("stroke"), "#40566A") if raw.get("stroke") != "none" else "none"
        item["stroke_width"] = max(0.0, min(16.0, _num(raw.get("stroke_width", 3), 3)))
        if item["type"] in {"polygon", "polyline"}:
            item["points"] = _points(raw.get("points"))
        if item["type"] in {"circle", "ellipse", "rect", "round_rect"}:
            for key in ("x", "y", "width", "height", "r", "rx"):
                if key in raw:
                    item[key] = _num(raw[key])
        if item["type"] == "line":
            for key in ("x1", "y1", "x2", "y2"):
                item[key] = _num(raw.get(key))
        if item["type"] == "text":
            item["x"], item["y"] = _num(raw.get("x", 64)), _num(raw.get("y", 70))
            item["text"] = re.sub(r"[<>]", "", str(raw.get("text", "")))[:28]
            item["font_size"] = max(7, min(28, int(_num(raw.get("font_size", 14), 14))))
        clean.append(item)
    return {"name": str(blueprint.get("name", "original concept"))[:60],
            "description": str(blueprint.get("description", ""))[:240],
            "elements": clean}

def _svg(data: dict[str, Any]) -> str:
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">']
    for e in data["elements"]:
        tag = e["type"]
        attrs = [f'fill="{e["fill"]}"', f'stroke="{e["stroke"]}"',
                 f'stroke-width="{e["stroke_width"]}"', 'stroke-linecap="round"',
                 'stroke-linejoin="round"']
        if tag == "circle":
            attrs += [f'cx="{_num(e.get("x",64))}"', f'cy="{_num(e.get("y",64))}"', f'r="{max(0,_num(e.get("r",20)))}"']
        elif tag == "ellipse":
            attrs += [f'cx="{_num(e.get("x",64))}"', f'cy="{_num(e.get("y",64))}"', f'rx="{max(0,_num(e.get("width",24))/2)}"', f'ry="{max(0,_num(e.get("height",24))/2)}"']
        elif tag in {"rect", "round_rect"}:
            attrs += [f'x="{_num(e.get("x"))}"', f'y="{_num(e.get("y"))}"',
                      f'width="{max(0,_num(e.get("width",20)))}"', f'height="{max(0,_num(e.get("height",20)))}"']
            if tag == "round_rect": attrs.append(f'rx="{max(0,_num(e.get("rx",8)))}"')
            tag = "rect"
        elif tag in {"polygon", "polyline"}:
            attrs.append('points="' + " ".join(f"{x},{y}" for x,y in e["points"]) + '"')
        elif tag == "line":
            attrs += [f'x1="{e["x1"]}"',f'y1="{e["y1"]}"',f'x2="{e["x2"]}"',f'y2="{e["y2"]}"']
        elif tag == "text":
            attrs += [f'x="{e["x"]}"',f'y="{e["y"]}"',
                      f'font-family="DejaVu Sans, sans-serif"',f'font-size="{e["font_size"]}"',
                      'font-weight="bold"']
        if tag == "text":
            parts.append("<text " + " ".join(attrs) + ">" + e["text"] + "</text>")
        else:
            parts.append("<" + tag + " " + " ".join(attrs) + "/>")
    parts.append("</svg>")
    return "".join(parts)

def _preview(data: dict[str, Any], size: int = 256) -> Image.Image:
    image = Image.new("RGBA", (size,size), (0,0,0,0))
    d = ImageDraw.Draw(image)
    s = size / 128
    def xy(v): return int(round(v*s))
    for e in data["elements"]:
        typ=e["type"]; fill=e["fill"]; stroke=e["stroke"]
        f=None if fill=="none" else fill
        o=None if stroke=="none" else stroke
        w=max(1,xy(e["stroke_width"]))
        if typ=="circle":
            x,y,r=xy(e.get("x",64)),xy(e.get("y",64)),xy(e.get("r",20))
            d.ellipse((x-r,y-r,x+r,y+r),fill=f,outline=o,width=w)
        elif typ=="ellipse":
            x,y=xy(e.get("x",64)),xy(e.get("y",64)); rx=xy(e.get("width",24)/2); ry=xy(e.get("height",24)/2)
            d.ellipse((x-rx,y-ry,x+rx,y+ry),fill=f,outline=o,width=w)
        elif typ in {"rect","round_rect"}:
            box=(xy(e.get("x",0)),xy(e.get("y",0)),xy(e.get("x",0)+e.get("width",20)),xy(e.get("y",0)+e.get("height",20)))
            if typ=="round_rect": d.rounded_rectangle(box, radius=xy(e.get("rx",8)), fill=f, outline=o, width=w)
            else: d.rectangle(box,fill=f,outline=o,width=w)
        elif typ in {"polygon","polyline"}:
            pts=[(xy(x),xy(y)) for x,y in e["points"]]
            if typ=="polygon": d.polygon(pts,fill=f,outline=o)
            else: d.line(pts,fill=o or f,width=w,joint="curve")
        elif typ=="line":
            d.line((xy(e["x1"]),xy(e["y1"]),xy(e["x2"]),xy(e["y2"])),fill=o or f,width=w)
        elif typ=="text":
            try: font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",xy(e["font_size"]))
            except OSError: font=ImageFont.load_default()
            d.text((xy(e["x"]),xy(e["y"])),e["text"],font=font,fill=f or o or "#40566A")
    return image

def create_concept_asset(blueprint: dict[str, Any], output_dir: Path) -> dict[str, str]:
    """Compile a new AI-authored vector blueprint into a hash-addressed SVG + PNG preview."""
    data=validate_blueprint(blueprint)
    svg=_svg(data)
    digest=hashlib.sha256(svg.encode("utf-8")).hexdigest()
    root=Path(output_dir)/"visual-library"
    root.mkdir(parents=True,exist_ok=True)
    svg_path=root/f"{digest}.svg"
    png_path=root/f"{digest}.png"
    if not svg_path.exists(): svg_path.write_text(svg,encoding="utf-8")
    if not png_path.exists(): _preview(data).save(png_path,optimize=True)
    manifest_path=Path(output_dir)/"visual-library-manifest.json"
    manifest={}
    if manifest_path.exists():
        try: manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError,OSError): manifest={}
    assets=manifest.setdefault("assets",{})
    asset_id="custom_"+digest[:12]
    assets[asset_id]={"sha256":digest,"path":str(svg_path.relative_to(output_dir)),
                      "preview":str(png_path.relative_to(output_dir)),"media_type":"image/svg+xml",
                      "kind":"generated_concept","name":data["name"],"description":data["description"]}
    manifest.update({"version":2,"assets":assets})
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return {"asset":asset_id,"sha256":digest,"svg_path":str(svg_path),"preview_path":str(png_path)}
