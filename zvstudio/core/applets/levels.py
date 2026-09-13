"""Level Bars applet — a static 16-step gray ramp.

The panel is 4-bit grayscale, so only 16 levels are displayable
(0, 16, 32, …, 240). This pattern shows each of them as a bar so you can
verify per-pixel levels and the software brightness scaling by eye.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .. import frame as F
from .base import Applet, AppletMeta, Ctx


class LevelBarsApplet(Applet):
    meta = AppletMeta(
        key="levels",
        name="Level Bars",
        description="16 gray-level test bars (0-240)",
        config_schema={"fps": {"type": "int", "default": 1, "label": "FPS"}},
    )

    def render(self, ctx: Ctx) -> Image.Image:
        w, h = self.size
        img = F.canvas(w, h)
        d = ImageDraw.Draw(img)
        n = 16
        bw = w / n
        for i in range(n):
            v = i * 16  # the 16 displayable 4-bit levels: 0, 16, …, 240
            d.rectangle([int(i * bw), 0, int((i + 1) * bw) - 1, h], fill=v)
        return img