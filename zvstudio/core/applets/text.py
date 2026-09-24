"""Text applet — scroll a custom message."""
from __future__ import annotations

from PIL import Image

from .. import frame as F
from .base import Applet, AppletMeta, Ctx


class TextApplet(Applet):
    meta = AppletMeta(
        key="text",
        name="Text",
        description="Scroll a custom message",
        config_schema={
            "text": {"type": "str", "default": "hello :)", "label": "Message"},
            "size": {"type": "int", "default": 30, "label": "Font size"},
            "speed": {"type": "int", "default": 50, "label": "Scroll px/s"},
            "fps": {"type": "int", "default": 20, "label": "FPS"},
        },
    )

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self._strip: Image.Image | None = None
        self._strip_key: tuple | None = None  # (msg, size) the cached strip was built for

    def render(self, ctx: Ctx) -> Image.Image:
        w, h = self.size
        img = F.canvas(w, h)
        msg = str(self.config.get("text") or "")
        if not msg:
            return img
        size = int(self.config.get("size", 30))
        key = (msg, size)
        if self._strip is None or self._strip_key != key:
            self._strip = F.render_text(msg, size)
            self._strip_key = key
        strip = self._strip
        if strip.width > w:
            F.scroll(strip, int(ctx.t * float(self.config.get("speed", 50))), img)
        else:
            img.paste(strip, ((w - strip.width) // 2, 0))
        return img
