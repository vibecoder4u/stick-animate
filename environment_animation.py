from __future__ import annotations

"""Procedural 2D environment plates and time-based environmental motion."""
import math
from typing import Any
from PIL import Image, ImageDraw

W, H = 1280, 720

def render_environment_background(base: Image.Image, kind: str, scene: dict[str, Any]) -> Image.Image:
    if kind not in {"beach", "ocean", "sea", "underwater"}:
        return base
    image = Image.new("RGB", (W,H), (0,0,0))
    d = ImageDraw.Draw(image)
    if kind == "underwater":
        for y in range(H):
            p=y/H
            c=(int(16-8*p),int(105-65*p),int(151-78*p))
            d.line((0,y,W,y),fill=c)
        d.polygon([(0,620),(140,560),(250,630),(390,570),(530,650),(720,590),(900,650),(1080,570),(1280,630),(1280,720),(0,720)],fill=(20,91,77))
    else:
        # Sky, distant horizon, sea and warm sand create a clear layered beach plate.
        for y in range(H):
            if y < 270:
                p=y/270
                c=(int(104+75*p),int(174+43*p),int(220+20*p))
            elif y < 525:
                p=(y-270)/255
                c=(int(25+8*p),int(133-12*p),int(177-18*p))
            else:
                p=(y-525)/195
                c=(int(224-9*p),int(196-17*p),int(139-13*p))
            d.line((0,y,W,y),fill=c)
        d.ellipse((930,72,1060,202),fill=(255,226,151))
        d.polygon([(0,525),(250,508),(520,530),(800,512),(1040,528),(1280,510),(1280,720),(0,720)],fill=(220,190,135))
    return image

def animate_environment(image: Image.Image, kind: str, scene: dict[str, Any], t: float) -> Image.Image:
    if kind not in {"beach", "ocean", "sea", "underwater"}:
        return image
    layer=Image.new("RGBA",(W,H),(0,0,0,0))
    d=ImageDraw.Draw(layer)
    if kind == "underwater":
        for i in range(22):
            x=(i*71+int(t*(9+i%4)))%W
            y=H-((i*97+int(t*(20+i%5)))%650)
            r=2+(i%4)
            d.ellipse((x-r,y-r,x+r,y+r),outline=(190,235,240,130),width=2)
        for i in range(8):
            x=80+i*160
            d.line((x,650,x+math.sin(t*1.4+i)*18,540),fill=(57,151,112,140),width=5)
    else:
        # Independent wave bands move at different speeds to create depth.
        for band,(y,amp,speed,alpha) in enumerate(((292,7,1.7,115),(350,11,1.25,125),(420,15,.85,145),(490,8,.6,110))):
            pts=[]
            for x in range(-20,W+21,20):
                yy=y+math.sin(x*.018+t*speed+band)*amp+math.sin(x*.007-t*speed*.6)*amp*.45
                pts.append((x,int(yy)))
            d.line(pts,fill=(205,239,244,alpha),width=3 if band<2 else 4)
            for j in range(7):
                x=(j*193+int(t*(24+band*9)))%W
                yy=y+24+j%3*12+math.sin(t*2+j)*3
                d.ellipse((x,yy,x+30,yy+3),fill=(225,245,239,65))
        # Shore foam pulses gently at the waterline.
        shore=520+math.sin(t*1.5)*5
        d.line([(0,int(shore)),(W//2,int(shore+math.sin(t)*4)),(W,int(shore-3))],fill=(245,249,231,180),width=5)
    return Image.alpha_composite(image.convert("RGBA"),layer).convert("RGB")
