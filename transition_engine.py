from __future__ import annotations
"""Soft scene blending and easing helpers for the story renderer."""
from PIL import Image

def smoothstep(x: float) -> float:
    x=max(0.0,min(1.0,float(x)))
    return x*x*(3.0-2.0*x)

def crossfade(current: Image.Image, previous: Image.Image, progress: float) -> Image.Image:
    """Blend prior shot into current shot using smoothstep progress."""
    return Image.blend(previous.convert('RGB'), current.convert('RGB'), smoothstep(progress)).convert('RGB')

def transition_duration(script: dict, scene: dict) -> float:
    cfg=script.get('transitions', {}) or {}
    if isinstance(cfg, (int,float)): return max(0.0,float(cfg))
    return max(0.0,float(cfg.get('duration', scene.get('transition_duration', 0.65))))
