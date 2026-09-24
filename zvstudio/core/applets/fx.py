"""More demoscene-style audio-reactive effects: moire, metaballs, ripple, fire,
matrix rain. Original implementations of classic public-domain techniques,
rendered in grayscale for the 256x64 panel.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from .. import frame as F
from .base import AppletMeta, Ctx
from .viz import HAVE_NP, TRAILS, _Viz

if HAVE_NP:
    import numpy as np


class MoireApplet(_Viz):
    meta = AppletMeta(key="moire", name="Moire", description="Interfering ring sources",
                      config_schema={"fps": {"type": "int", "default": 30, "label": "FPS"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"},
                                     "trails": {**TRAILS, "default": 40}})

    def render(self, ctx: Ctx):
        if not HAVE_NP:
            return self._pulse(ctx)
        gx, gy = self._grids()
        a = self._audio
        audio = self.config.get("audio", False)
        t = ctx.t
        bass = a.bass if audio and a.ok else 0.0
        lvl = a.level if audio and a.ok else 0.5
        asp = self.size[0] / self.size[1]
        x = gx * asp
        f1 = (asp * (0.5 + 0.35 * math.sin(t * 0.7)), 0.5 + 0.35 * math.cos(t * 0.9))
        f2 = (asp * (0.5 + 0.35 * math.sin(t * 1.1 + 2)), 0.5 + 0.35 * math.cos(t * 0.6 + 1))
        d1 = np.sqrt((x - f1[0]) ** 2 + (gy - f1[1]) ** 2)
        d2 = np.sqrt((x - f2[0]) ** 2 + (gy - f2[1]) ** 2)
        k = 28 + 22 * bass
        v = np.cos(d1 * k - t * 2) + np.cos(d2 * k + t * 1.5)
        v = (v + 2) / 4
        g = v * (0.5 + 0.5 * lvl) * 255.0
        return self._feedback(g)


class MetaballsApplet(_Viz):
    meta = AppletMeta(key="metaballs", name="Metaballs", description="Gooey blobs",
                      config_schema={"fps": {"type": "int", "default": 30, "label": "FPS"},
                                     "balls": {"type": "int", "default": 4, "label": "Blobs"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"},
                                     "trails": {**TRAILS, "default": 35}})

    def render(self, ctx: Ctx):
        if not HAVE_NP:
            return self._pulse(ctx)
        w, h = self.size
        gx, gy = self._grids()
        px, py = gx * w, gy * h
        a = self._audio
        t = ctx.t
        lvl = a.level if self.config.get("audio", False) and a.ok else 0.5
        nb = max(2, int(self.config.get("balls", 4)))
        field = np.zeros((h, w), np.float32)
        rad = (h * 0.42) * (0.7 + 0.5 * lvl)
        for i in range(nb):
            bx = w * (0.5 + 0.42 * math.sin(t * (0.5 + 0.2 * i) + i))
            by = h * (0.5 + 0.42 * math.cos(t * (0.4 + 0.25 * i) + i * 2))
            field += (rad * rad) / ((px - bx) ** 2 + (py - by) ** 2 + 1.0)
        g = np.clip((field - 0.8) * 200, 0, 255)
        return self._feedback(g.astype(np.float32))


class RippleApplet(_Viz):
    meta = AppletMeta(key="ripple", name="Ripple", description="Water ripples (beat drops)",
                      config_schema={"fps": {"type": "int", "default": 30, "label": "FPS"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"}})

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self._cur = self._prev = None
        self._last_beat = 0.0

    def render(self, ctx: Ctx):
        w, h = self.size
        if not HAVE_NP:
            return self._pulse(ctx)
        if self._cur is None or self._cur.shape != (h, w):
            self._cur = np.zeros((h, w), np.float32)
            self._prev = np.zeros((h, w), np.float32)
        a = self._audio
        cur, prev = self._cur, self._prev
        lap = (np.roll(cur, 1, 0) + np.roll(cur, -1, 0) + np.roll(cur, 1, 1) + np.roll(cur, -1, 1))
        nxt = lap * 0.5 - prev
        nxt *= 0.96
        # drop on beat, plus a gentle idle drop
        audio = self.config.get("audio", False)
        beat = a.beat if audio and a.ok else 0
        if beat > 0.4 and beat > self._last_beat:
            nxt[random.randint(2, h - 3), random.randint(2, w - 3)] += 260
        self._last_beat = beat
        if int(ctx.t * 2) != int((ctx.t - 0.05) * 2) and beat <= 0.4:
            nxt[h // 2, random.randint(2, w - 3)] += 120
        self._prev, self._cur = cur, nxt
        g = np.clip(np.abs(nxt) * 7.0, 0, 255).astype(np.uint8)   # dark water, bright ripples
        from PIL import Image
        return Image.fromarray(g, "L")


class FireApplet(_Viz):
    meta = AppletMeta(key="fire", name="Fire", description="Classic fire (bass-fed)",
                      config_schema={"fps": {"type": "int", "default": 30, "label": "FPS"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"}})

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self._fire = None

    def render(self, ctx: Ctx):
        w, h = self.size
        if not HAVE_NP:
            return self._pulse(ctx)
        if self._fire is None or self._fire.shape != (h, w):
            self._fire = np.zeros((h, w), np.float32)
        a = self._audio
        bass = a.bass if self.config.get("audio", False) and a.ok else 0.4
        fire = self._fire
        below = np.roll(fire, -1, 0)
        nxt = (below * 2 + np.roll(below, 1, 1) + np.roll(below, -1, 1)) / 4.04 - 3.0
        nxt = np.clip(nxt, 0, 255)
        nxt[-1] = np.random.rand(w) * 255 * (0.55 + 0.6 * bass)
        self._fire = nxt
        from PIL import Image
        return Image.fromarray(nxt.astype(np.uint8), "L")


class MatrixApplet(_Viz):
    meta = AppletMeta(key="matrix", name="Matrix", description="Falling katakana rain",
                      config_schema={"fps": {"type": "int", "default": 24, "label": "FPS"},
                                     "size": {"type": "int", "default": 9, "label": "Glyph size (smaller = denser)"},
                                     "speed": {"type": "int", "default": 150, "label": "Speed %"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"}})

    GLYPH = ("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
             "マミムメモヤユヨラリルレロワヲンｱｲｳｴｵ0123456789")

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self._heads: list[float] | None = None
        self._glyphs: list[list[tuple[Image.Image, int, int]]] = []  # [level][char] -> (cell, dx, dy)
        self._level_of_kk: list[int] = []  # tail row index -> fade level index
        self._ch = self._tail = 0
        self._lt = 0.0

    def _build(self, ch: int, tail: int) -> None:
        """Rasterize every glyph once per fade level; per-frame we only blit the
        cached bitmaps, which is far cheaper than FreeType text rendering."""
        f = F.cjk_font(ch)
        pad = ch  # headroom so negative font bearings never clip
        base: list[tuple[Image.Image, int, int]] = []
        for glyph in self.GLYPH:
            buf = Image.new("L", (ch + 2 * pad, ch + 2 * pad), 0)
            ImageDraw.Draw(buf).text((pad, pad), glyph, font=f, fill=255)
            bbox = buf.getbbox()
            if bbox is None:
                base.append((Image.new("L", (1, 1), 0), 0, 0))
                continue
            base.append((buf.crop(bbox), bbox[0] - pad, bbox[1] - pad))
        levels: list[int] = []
        self._glyphs = []
        self._level_of_kk = []
        for kk in range(tail):
            gv = 255 if kk == 0 else max(30, int(220 - kk * 200 / tail))
            if gv not in levels:
                levels.append(gv)
                lut = bytes(round(v * gv / 255) for v in range(256))
                self._glyphs.append([(g.point(lut), dx, dy) for g, dx, dy in base])
            self._level_of_kk.append(levels.index(gv))
        self._ch = ch
        self._tail = tail

    def render(self, ctx: Ctx):
        w, h = self.size
        a = self._audio
        ch = max(6, int(self.config.get("size", 9)))
        cw = max(4, int(ch * 0.78))
        cols = max(1, w // cw)
        tail = int(h / ch) + 3
        if self._heads is None or len(self._heads) != cols or self._ch != ch or self._tail != tail:
            self._heads = [random.uniform(-h, 0) for _ in range(cols)]
            self._build(ch, tail)
        dt = max(0.0, min(0.1, ctx.t - self._lt))
        self._lt = ctx.t
        speedf = max(0.2, self.config.get("speed", 150) / 100.0)
        audio = self.config.get("audio", False)
        level = a.level if audio and a.ok else 0.4
        spd = ch * (0.6 + 1.8 * level) * speedf  # px per second
        img = F.canvas(w, h)
        glyphs = self._glyphs
        level_of_kk = self._level_of_kk
        n = len(self.GLYPH)
        for c in range(cols):
            hy = self._heads[c] + spd * dt
            if hy - tail * ch > h:
                hy = random.uniform(-h * 0.5, 0)
            self._heads[c] = hy
            x = c * cw
            for kk in range(tail):
                y = hy - kk * ch
                if -ch < y < h:
                    cell, dx, dy = glyphs[level_of_kk[kk]][random.randrange(n)]
                    img.paste(cell, (x + dx, int(y) + dy))
        return img
