"""Gradient applet — a smooth gray gradient for counting displayable shades.

The panel is 4-bit grayscale, so every 16 gray levels collapse into one band
(0..15 -> 0, 16..31 -> 1, …). A gradient shows the bands as continuous
columns, letting you count the visible steps by eye - including how they
merge when the software brightness scales them down.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .. import frame as F
from .base import Applet, AppletMeta, Ctx


class GradientApplet(Applet):
    meta = AppletMeta(
        key="gradient",
        name="Gradient",
        description="Smooth gray gradient",
        config_schema={"fps": {"type": "int", "default": 1, "label": "FPS"}},
    )

    def render(self, ctx: Ctx) -> Image.Image:
        w, h = self.size
        img = F.canvas(w, h)
        d = ImageDraw.Draw(img)
        for x in range(w):
            v = int(x * 255 / (w - 1))
            d.line([(x, 0), (x, h - 1)], fill=v)
        return img