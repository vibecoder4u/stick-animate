from __future__ import annotations

"""Animated explanatory sticker library rendered with Pillow vector primitives.

Sticker timing is scene-local (0..1). The renderer composites RGBA overlays onto
RGB or RGBA frames so transparency and animation work consistently in CI.
"""
from typing import Any
import math
from PIL import Image, ImageDraw, ImageFont

STICKERS = {
    "idea": {"category":"reaction","label":"Idea bulb"},
    "question": {"category":"reaction","label":"Question mark"},
    "exclamation": {"category":"reaction","label":"Exclamation"},
    "brain": {"category":"science","label":"Brain"},
    "book": {"category":"education","label":"Book"},
    "clock": {"category":"time","label":"Clock"},
    "arrow_up": {"category":"explanation","label":"Up arrow"},
    "check": {"category":"status","label":"Check mark"},
    "sparkles": {"category":"effect","label":"Sparkles"},
    "heart": {"category":"reaction","label":"Heart"},
    "neuron": {"category":"science","label":"Neuron"},
    "magnify": {"category":"explanation","label":"Magnifier"},
}

# Keep editable SVG source alongside the Pillow renderer for every catalogue item.
_SVG_SHAPES = {
    "idea": '<path d="M50 8a29 29 0 0 0-18 52v12h36V60A29 29 0 0 0 50 8Z" fill="#F6BE3A" stroke="#253141" stroke-width="5"/><path d="M39 82h22M42 91h16" stroke="#253141" stroke-width="5"/>',
    "question": '<path d="M27 34Q30 10 54 12Q80 14 77 37Q76 51 53 61V70" fill="none" stroke="#41A5DC" stroke-width="13" stroke-linecap="round"/><circle cx="53" cy="88" r="7" fill="#41A5DC"/>',
    "exclamation": '<path d="M50 12v49" stroke="#EB5B49" stroke-width="15" stroke-linecap="round"/><circle cx="50" cy="85" r="8" fill="#EB5B49"/>',
    "brain": '<path d="M49 18C28 2 10 25 22 41C5 54 23 82 43 75C49 91 62 83 61 72C83 82 96 58 79 44C91 22 67 7 55 22Z" fill="#EE91B2" stroke="#713C5A" stroke-width="5"/>',
    "book": '<path d="M10 20Q34 12 50 29Q66 12 90 20V79Q65 70 50 87Q35 70 10 79Z" fill="#4D9DD3" stroke="#234B68" stroke-width="5"/>',
    "clock": '<circle cx="50" cy="50" r="38" fill="#F5F5F2" stroke="#46596C" stroke-width="7"/><path d="M50 25v27l20 12" fill="none" stroke="#46596C" stroke-width="7" stroke-linecap="round"/>',
    "arrow_up": '<path d="M50 8 12 49h22v42h32V49h22Z" fill="#43B27E" stroke="#235B47" stroke-width="5"/>',
    "check": '<path d="m15 52 23 23 48-52" fill="none" stroke="#37B16F" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>',
    "sparkles": '<path d="M50 5 60 39 95 50 60 61 50 95 40 61 5 50 40 39Z" fill="#F9C642"/>',
    "heart": '<path d="M50 88 15 52C-5 25 27 2 50 29 73 2 105 25 85 52Z" fill="#E85E80" stroke="#7B3446" stroke-width="5"/>',
    "neuron": '<circle cx="50" cy="50" r="12" fill="#F5C85C"/><g stroke="#8597DA" stroke-width="6" stroke-linecap="round"><path d="M50 38 50 8M40 43 15 22M60 43 85 20M38 55 10 73M62 56 90 76M50 62 50 94"/></g>',
    "magnify": '<circle cx="42" cy="40" r="27" fill="none" stroke="#5291CF" stroke-width="10"/><path d="m62 62 27 27" stroke="#5291CF" stroke-width="13" stroke-linecap="round"/>',
}
for _sid, _item in STICKERS.items():
    _item["svg"] = '<svg viewBox="0 0 100 100">' + _SVG_SHAPES[_sid] + '</svg>'

PALETTE = {
    "idea": (246,190,58), "question": (65,165,220), "exclamation": (235,91,73),
    "brain": (238,145,178), "book": (77,157,211), "clock": (93,116,139),
    "arrow_up": (67,178,126), "check": (55,177,111), "sparkles": (249,198,66),
    "heart": (232,94,128), "neuron": (133,151,218), "magnify": (82,145,207),
}

def sticker_catalog() -> dict[str, Any]:
    return {key: dict(value) for key, value in STICKERS.items()}

def _font(size: int, bold: bool = True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, max(10, size))
        except OSError:
            pass
    return ImageFont.load_default()

def _ease_out_back(value: float) -> float:
    c1, c3 = 1.70158, 2.70158
    x = max(0.0, min(1.0, value)) - 1.0
    return 1.0 + c3*x*x*x + c1*x*x

def _draw_symbol(draw: ImageDraw.ImageDraw, sid: str, cx: float, cy: float,
                 size: float, color: tuple[int,int,int], alpha: int) -> None:
    s = size
    ink = (37, 49, 65, alpha)
    fill = (*color, alpha)
    width = max(3, int(s * 0.065))
    if sid == "idea":
        draw.ellipse((cx-s*.25,cy-s*.34,cx+s*.25,cy+s*.12),fill=fill,outline=ink,width=max(2,width//2))
        draw.rounded_rectangle((cx-s*.15,cy+s*.08,cx+s*.15,cy+s*.25),radius=max(2,int(s*.04)),fill=(232,239,244,alpha),outline=ink,width=2)
        draw.line((cx-s*.11,cy+s*.30,cx+s*.11,cy+s*.30),fill=ink,width=max(2,width//2))
        for dx,dy in ((0,-.48),(-.42,-.18),(.42,-.18)):
            draw.line((cx+dx*s*.72,cy+dy*s*.72,cx+dx*s,cy+dy*s),fill=fill,width=max(2,width//2))
    elif sid == "question":
        draw.arc((cx-s*.28,cy-s*.35,cx+s*.28,cy+s*.12),185,525,fill=fill,width=width)
        draw.line((cx,cy+s*.12,cx,cy+s*.25),fill=fill,width=width)
        draw.ellipse((cx-s*.035,cy+s*.34,cx+s*.035,cy+s*.41),fill=fill)
    elif sid == "exclamation":
        draw.rounded_rectangle((cx-s*.055,cy-s*.36,cx+s*.055,cy+s*.15),radius=max(2,int(s*.04)),fill=fill)
        draw.ellipse((cx-s*.06,cy+s*.28,cx+s*.06,cy+s*.40),fill=fill)
    elif sid == "brain":
        draw.ellipse((cx-s*.32,cy-s*.24,cx+s*.02,cy+s*.27),fill=fill,outline=ink,width=2)
        draw.ellipse((cx-s*.02,cy-s*.28,cx+s*.32,cy+s*.24),fill=fill,outline=ink,width=2)
        for dx in (-.17,-.06,.08,.19):
            draw.arc((cx+dx*s-s*.10,cy-s*.16,cx+dx*s+s*.12,cy+s*.18),70,280,fill=(143,67,104,alpha),width=max(2,width//3))
        draw.line((cx,cy-s*.22,cx,cy+s*.22),fill=ink,width=2)
    elif sid == "book":
        draw.polygon([(cx-s*.34,cy-s*.24),(cx-s*.03,cy-s*.16),(cx,cy-s*.07),(cx,cy+s*.32),(cx-s*.34,cy+s*.20)],fill=fill,outline=ink)
        draw.polygon([(cx+s*.34,cy-s*.24),(cx+s*.03,cy-s*.16),(cx,cy-s*.07),(cx,cy+s*.32),(cx+s*.34,cy+s*.20)],fill=(116,190,231,alpha),outline=ink)
        draw.line((cx,cy-s*.06,cx,cy+s*.31),fill=ink,width=2)
        for yy in (-.08,.04,.15):
            draw.line((cx-s*.25,cy+yy*s,cx-s*.08,cy+(yy+.04)*s),fill=(255,255,255,alpha),width=2)
            draw.line((cx+s*.08,cy+(yy+.04)*s,cx+s*.25,cy+yy*s),fill=(255,255,255,alpha),width=2)
    elif sid == "clock":
        draw.ellipse((cx-s*.32,cy-s*.32,cx+s*.32,cy+s*.32),fill=(246,249,250,alpha),outline=ink,width=width)
        draw.line((cx,cy,cx,cy-s*.20),fill=ink,width=width)
        draw.line((cx,cy,cx+s*.18,cy+s*.12),fill=ink,width=width)
    elif sid == "arrow_up":
        draw.polygon([(cx,cy-s*.40),(cx-s*.31,cy-s*.02),(cx-s*.13,cy-s*.02),(cx-s*.13,cy+s*.34),(cx+s*.13,cy+s*.34),(cx+s*.13,cy-s*.02),(cx+s*.31,cy-s*.02)],fill=fill,outline=ink)
    elif sid == "check":
        draw.line((cx-s*.31,cy,cx-s*.08,cy+s*.23,cx+s*.34,cy-s*.28),fill=fill,width=max(7,int(s*.13)),joint="curve")
    elif sid == "sparkles":
        for ox,oy,r in ((0,0,.34),(-.29,.22,.13),(.28,-.24,.11)):
            x,y=cx+ox*s,cy+oy*s
            draw.polygon([(x,y-r*s),(x+r*.23*s,y-r*.23*s),(x+r*s,y),(x+r*.23*s,y+r*.23*s),(x,y+r*s),(x-r*.23*s,y+r*.23*s),(x-r*s,y),(x-r*.23*s,y-r*.23*s)],fill=fill)
    elif sid == "heart":
        draw.polygon([(cx,cy+s*.34),(cx-s*.34,cy),(cx-s*.30,cy-s*.23),(cx-s*.12,cy-s*.29),(cx,cy-s*.13),(cx+s*.12,cy-s*.29),(cx+s*.30,cy-s*.23),(cx+s*.34,cy)],fill=fill,outline=ink)
    elif sid == "neuron":
        draw.ellipse((cx-s*.13,cy-s*.13,cx+s*.13,cy+s*.13),fill=fill,outline=ink,width=2)
        for angle in range(0,360,45):
            a=math.radians(angle)
            x1,y1=cx+math.cos(a)*s*.12,cy+math.sin(a)*s*.12
            x2,y2=cx+math.cos(a)*s*.39,cy+math.sin(a)*s*.39
            draw.line((x1,y1,x2,y2),fill=fill,width=max(3,int(s*.045)))
            draw.ellipse((x2-s*.035,y2-s*.035,x2+s*.035,y2+s*.035),fill=fill)
    elif sid == "magnify":
        draw.ellipse((cx-s*.31,cy-s*.34,cx+s*.12,cy+s*.09),fill=(255,255,255,alpha),outline=fill,width=width)
        draw.line((cx+s*.08,cy+s*.08,cx+s*.36,cy+s*.36),fill=fill,width=max(6,int(s*.10)))

def draw_stickers(image: Image.Image, scene: dict, local_t: float = 0.5) -> None:
    """Draw animated sticker overlays; x/y are normalized canvas coordinates."""
    stickers = scene.get("stickers") or []
    if not stickers:
        return
    w,h = image.size
    base_mode = image.mode
    canvas = image.convert("RGBA")
    for index,item in enumerate(stickers):
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id","")).lower()
        if sid not in STICKERS:
            continue
        start = max(0.0,min(1.0,float(item.get("start",0.0))))
        end = max(start+0.001,min(1.0,float(item.get("end",1.0))))
        if local_t < start or local_t > end:
            continue
        progress = max(0.0,min(1.0,(local_t-start)/(end-start)))
        entrance = min(1.0,progress/0.22)
        exit_fade = min(1.0,max(0.0,(1.0-progress)/0.10))
        anim = str(item.get("animation","pop" if index % 2 == 0 else "float")).lower()
        if anim == "none":
            scale_factor,dx,dy,rotation = 1.0,0.0,0.0,0.0
        elif anim == "pop":
            scale_factor = max(.12,_ease_out_back(entrance))
            dx,dy,rotation = 0.0, (1.0-entrance)*12.0, (1.0-entrance)*-8.0
        elif anim == "bounce":
            scale_factor = .88 + .12*_ease_out_back(entrance)
            dx = 0.0
            dy = (1.0-entrance)*18.0 + math.sin(progress*math.tau*2)*4.0
            rotation = math.sin(progress*math.tau)*4.0
        elif anim == "float":
            scale_factor = 1.0 + .025*math.sin(progress*math.tau*2)
            dx,dy,rotation = 0.0, math.sin(progress*math.tau*2)*10.0, math.sin(progress*math.tau)*2.0
        elif anim == "pulse":
            scale_factor = 1.0 + .10*(.5+.5*math.sin(progress*math.tau*2))
            dx,dy,rotation = 0.0,0.0,0.0
        elif anim == "spin":
            scale_factor,dx,dy,rotation = 1.0,0.0,0.0,progress*360.0
        else:
            scale_factor,dx,dy,rotation = 1.0,0.0,0.0,0.0
        size = max(28,min(320,int(float(item.get("size",132))*scale_factor)))
        cx = int(float(item.get("x",.82))*w + dx)
        cy = int(float(item.get("y",.30))*h + dy)
        alpha = int(255*max(0.0,min(1.0,float(item.get("opacity",1.0))))*exit_fade)
        if alpha <= 0:
            continue
        tile_size = size + max(16,int(size*.30))
        tile = Image.new("RGBA",(tile_size,tile_size),(0,0,0,0))
        td = ImageDraw.Draw(tile)
        ox=oy=tile_size/2
        color=PALETTE[sid]
        shadow=(5,10,18,int(alpha*.28))
        td.ellipse((ox-size*.49+4,oy-size*.49+7,ox+size*.49+4,oy+size*.49+7),fill=shadow)
        td.ellipse((ox-size*.49,oy-size*.49,ox+size*.49,oy+size*.49),fill=(255,255,255,int(alpha*.98)),outline=(30,45,61,alpha),width=max(2,size//38))
        td.ellipse((ox-size*.40,oy-size*.40,ox+size*.40,oy+size*.40),fill=(*color,int(alpha*.16)))
        _draw_symbol(td,sid,ox,oy,size*.78,color,alpha)
        label=str(item.get("text","")).strip()
        if label:
            f=_font(max(11,min(24,size//6)))
            box=td.textbbox((0,0),label,font=f)
            tw=box[2]-box[0]
            label_y=oy+size*.56
            td.rounded_rectangle((ox-tw/2-8,label_y,ox+tw/2+8,label_y+25),radius=8,fill=(8,17,29,alpha))
            td.text((ox-tw/2,label_y+3),label,font=f,fill=(248,250,252,alpha))
        if rotation:
            tile=tile.rotate(rotation,resample=Image.Resampling.BICUBIC,expand=False)
        px,py=cx-tile_size//2,cy-tile_size//2
        layer=Image.new("RGBA",(w,h),(0,0,0,0))
        layer.alpha_composite(tile,(px,py))
        canvas=Image.alpha_composite(canvas,layer)
    if base_mode == "RGB":
        image.paste(canvas.convert("RGB"))
    else:
        image.paste(canvas)
