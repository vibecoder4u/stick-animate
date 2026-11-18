from __future__ import annotations
"""Reusable explanatory sticker catalogue and lightweight Pillow vector renderer.

SVG source strings are provided for editing/export. The runtime draws the same
symbols with Pillow primitives, avoiding an SVG rasterizer dependency.
"""
from typing import Any
from PIL import Image, ImageDraw, ImageFont
import math

STICKERS = {
    "idea":{"category":"reaction","label":"Idea bulb","svg":'<svg viewBox="0 0 100 100"><path d="M50 8a29 29 0 0 0-18 52v12h36V60A29 29 0 0 0 50 8Z" fill="#FFD45C" stroke="#513E26" stroke-width="5"/><path d="M39 82h22M42 91h16" stroke="#513E26" stroke-width="5"/></svg>'},
    "question":{"category":"reaction","label":"Question mark","svg":'<svg viewBox="0 0 100 100"><path d="M27 34Q30 10 54 12Q80 14 77 37Q76 51 53 61V70" fill="none" stroke="#4DA6D8" stroke-width="13" stroke-linecap="round"/><circle cx="53" cy="88" r="7" fill="#4DA6D8"/></svg>'},
    "exclamation":{"category":"reaction","label":"Exclamation","svg":'<svg viewBox="0 0 100 100"><path d="M50 12v49" stroke="#F06A57" stroke-width="15" stroke-linecap="round"/><circle cx="50" cy="85" r="8" fill="#F06A57"/></svg>'},
    "brain":{"category":"science","label":"Brain","svg":'<svg viewBox="0 0 100 100"><path d="M49 18C28 2 10 25 22 41C5 54 23 82 43 75C49 91 62 83 61 72C83 82 96 58 79 44C91 22 67 7 55 22Z" fill="#F29AB4" stroke="#693D58" stroke-width="5"/></svg>'},
    "book":{"category":"education","label":"Book","svg":'<svg viewBox="0 0 100 100"><path d="M10 20Q34 12 50 29Q66 12 90 20V79Q65 70 50 87Q35 70 10 79Z" fill="#72B8E8" stroke="#234B68" stroke-width="5"/></svg>'},
    "clock":{"category":"time","label":"Clock","svg":'<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="38" fill="#F5F5F2" stroke="#46596C" stroke-width="7"/><path d="M50 25v27l20 12" fill="none" stroke="#46596C" stroke-width="7" stroke-linecap="round"/></svg>'},
    "arrow_up":{"category":"explanation","label":"Up arrow","svg":'<svg viewBox="0 0 100 100"><path d="M50 8 12 49h22v42h32V49h22Z" fill="#58B98A" stroke="#235B47" stroke-width="5"/></svg>'},
    "check":{"category":"status","label":"Check mark","svg":'<svg viewBox="0 0 100 100"><path d="m15 52 23 23 48-52" fill="none" stroke="#50B77D" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/></svg>'},
    "sparkles":{"category":"effect","label":"Sparkles","svg":'<svg viewBox="0 0 100 100"><path d="M50 5 60 39 95 50 60 61 50 95 40 61 5 50 40 39Z" fill="#FFD45C"/></svg>'},
    "heart":{"category":"reaction","label":"Heart","svg":'<svg viewBox="0 0 100 100"><path d="M50 88 15 52C-5 25 27 2 50 29 73 2 105 25 85 52Z" fill="#F06D83" stroke="#7B3446" stroke-width="5"/></svg>'},
    "neuron":{"category":"science","label":"Neuron","svg":'<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="12" fill="#F5C85C"/><g stroke="#6B83B5" stroke-width="6" stroke-linecap="round"><path d="M50 38 50 8M40 43 15 22M60 43 85 20M38 55 10 73M62 56 90 76M50 62 50 94"/></g></svg>'},
    "magnify":{"category":"explanation","label":"Magnifier","svg":'<svg viewBox="0 0 100 100"><circle cx="42" cy="40" r="27" fill="none" stroke="#5C91C9" stroke-width="10"/><path d="m62 62 27 27" stroke="#5C91C9" stroke-width="13" stroke-linecap="round"/></svg>'},
}

def sticker_catalog() -> dict[str, Any]:
    return {key: {k:v for k,v in item.items() if k != "svg"} for key,item in STICKERS.items()}

def draw_stickers(image, scene: dict, local_t: float = 0.5) -> None:
    """Draw scene sticker overlays. x/y are normalized canvas coordinates."""
    if not scene.get("stickers"):
        return
    d = ImageDraw.Draw(image, "RGBA")
    w,h = image.size
    for item in scene.get("stickers", []):
        start=float(item.get("start",0)); end=float(item.get("end",1))
        if local_t < start or local_t > end:
            continue
        sid=str(item.get("id","")).lower()
        if sid not in STICKERS:
            continue
        x=int(float(item.get("x",0.82))*w); y=int(float(item.get("y",0.32))*h)
        size=max(18,min(220,int(item.get("size",76))))
        alpha=max(0,min(255,int(255*float(item.get("opacity",1.0)))))
        box=(x-size//2,y-size//2,x+size//2,y+size//2)
        d.ellipse(box,fill=(255,255,255,int(alpha*.94)),outline=(31,48,65,alpha),width=max(2,size//24))
        color={"idea":(245,190,55),"question":(55,151,210),"exclamation":(231,91,72),"brain":(236,139,171),"book":(76,151,205),"clock":(91,113,135),"arrow_up":(65,169,120),"check":(55,165,104),"sparkles":(244,187,52),"heart":(226,89,119),"neuron":(117,137,195),"magnify":(76,133,193)}[sid]
        cx,cy=x,y
        if sid in {"question","exclamation"}:
            mark="?" if sid=="question" else "!"
            try: f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",int(size*.78))
            except OSError: f=ImageFont.load_default()
            d.text((cx-size*.24,cy-size*.48),mark,font=f,fill=(*color,alpha),stroke_width=1)
        elif sid=="brain":
            d.ellipse((cx-size*.32,cy-size*.25,cx+size*.32,cy+size*.25),fill=(*color,alpha),outline=(113,60,90,alpha),width=3)
            d.arc((cx-size*.2,cy-size*.2,cx,cy+size*.2),270,90,fill=(130,65,99,alpha),width=3)
            d.arc((cx,cy-size*.2,cx+size*.2,cy+size*.2),90,270,fill=(130,65,99,alpha),width=3)
        elif sid=="book":
            d.polygon([(cx-size*.34,cy-size*.25),(cx,cy-size*.13),(cx,cy+size*.3),(cx-size*.34,cy+size*.2)],fill=(*color,alpha))
            d.polygon([(cx,cy-size*.13),(cx+size*.34,cy-size*.25),(cx+size*.34,cy+size*.2),(cx,cy+size*.3)],fill=(113,185,226,alpha))
            d.line((cx,cy-size*.12,cx,cy+size*.3),fill=(35,72,99,alpha),width=3)
        elif sid=="clock":
            d.ellipse((cx-size*.3,cy-size*.3,cx+size*.3,cy+size*.3),outline=(*color,alpha),width=max(3,size//14))
            d.line((cx,cy,cx,cy-size*.18),fill=(*color,alpha),width=max(3,size//15))
            d.line((cx,cy,cx+size*.17,cy+size*.12),fill=(*color,alpha),width=max(3,size//15))
        elif sid=="arrow_up":
            d.polygon([(cx,cy-size*.32),(cx-size*.28,cy-size*.02),(cx-size*.11,cy-size*.02),(cx-size*.11,cy+size*.3),(cx+size*.11,cy+size*.3),(cx+size*.11,cy-size*.02),(cx+size*.28,cy-size*.02)],fill=(*color,alpha))
        elif sid=="check":
            d.line((cx-size*.28,cy,cx-size*.06,cy+size*.22,cx+size*.32,cy-size*.25),fill=(*color,alpha),width=max(5,size//9),joint="curve")
        elif sid=="sparkles":
            d.polygon([(cx,cy-size*.35),(cx+size*.1,cy-size*.08),(cx+size*.35,cy),(cx+size*.1,cy+size*.08),(cx,cy+size*.35),(cx-size*.1,cy+size*.08),(cx-size*.35,cy),(cx-size*.1,cy-size*.08)],fill=(*color,alpha))
        elif sid=="heart":
            d.polygon([(cx,cy+size*.3),(cx-size*.32,cy-size*.03),(cx-size*.28,cy-size*.25),(cx,cy-size*.08),(cx+size*.28,cy-size*.25),(cx+size*.32,cy-size*.03)],fill=(*color,alpha))
        elif sid=="neuron":
            d.ellipse((cx-size*.1,cy-size*.1,cx+size*.1,cy+size*.1),fill=(*color,alpha))
            for dx,dy in ((0,-.34),(-.3,-.2),(.3,-.2),(-.34,.23),(.34,.23),(0,.35)):
                d.line((cx,cy,cx+int(size*dx),cy+int(size*dy)),fill=(*color,alpha),width=max(3,size//16))
        elif sid=="magnify":
            d.ellipse((cx-size*.27,cy-size*.27,cx+size*.12,cy+size*.12),outline=(*color,alpha),width=max(4,size//12))
            d.line((cx+size*.08,cy+size*.08,cx+size*.33,cy+size*.33),fill=(*color,alpha),width=max(5,size//10))
        else:
            d.ellipse((cx-size*.16,cy-size*.16,cx+size*.16,cy+size*.16),fill=(*color,alpha))
        label=str(item.get("text",""))
        if label:
            try: f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",max(12,size//5))
            except OSError: f=ImageFont.load_default()
            tw=d.textbbox((0,0),label,font=f)[2]
            d.rounded_rectangle((cx-tw//2-9,cy+size*.57,cx+tw//2+9,cy+size*.57+28),radius=8,fill=(8,17,29,alpha))
            d.text((cx-tw//2,cy+size*.57+4),label,font=f,fill=(245,248,252,alpha))
