"""Geometric / demoscene visualisers — nested triangles, a wireframe cube and a
starfield. They animate on time, react to the audio (level / bass / beat) and
reuse the viz feedback buffer for MilkDrop-style trails.
"""
from __future__ import annotations

import math

from PIL import ImageDraw

from .. import frame as F
from .base import AppletMeta, Ctx
from .viz import HAVE_NP, TRAILS, _Viz

if HAVE_NP:
    import numpy as np


def _poly(cx, cy, r, sides, rot):
    return [(cx + r * math.cos(rot + 2 * math.pi * k / sides),
             cy + r * math.sin(rot + 2 * math.pi * k / sides)) for k in range(sides)]


class TrianglesApplet(_Viz):
    meta = AppletMeta(key="triangles", name="Triangles", description="Nested rotating triangles",
                      config_schema={"fps": {"type": "int", "default": 30, "label": "FPS"},
                                     "layers": {"type": "int", "default": 6, "label": "Layers"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"},
                                     "trails": {**TRAILS, "default": 55}})

    def render(self, ctx: Ctx):
        w, h = self.size
        img = F.canvas(w, h)
        d = ImageDraw.Draw(img)
        a = self._audio
        t = ctx.t
        audio = self.config.get("audio", True)
        lvl = a.level if audio and a.ok else 0.5 - 0.5 * math.cos(t * 1.5)
        bass = a.bass if audio and a.ok else lvl
        layers = max(1, int(self.config.get("layers", 6)))
        base = min(w, h) * (0.46 + 0.18 * lvl)
        cx, cy = w / 2, h / 2
        for i in range(layers):
            f = 1 - i / layers
            r = base * f
            rot = t * (0.5 + 0.6 * bass) * (1 if i % 2 == 0 else -1) + i * 0.5
            g = int(70 + 185 * f)
            d.polygon(_poly(cx, cy, r, 3, rot), outline=g)
        if HAVE_NP:
            return self._feedback(np.asarray(img, dtype=np.float32))
        return img


class CubeApplet(_Viz):
    meta = AppletMeta(key="cube", name="Cube", description="Rotating wireframe cube",
                      config_schema={"fps": {"type": "int", "default": 30, "label": "FPS"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"},
                                     "trails": {**TRAILS, "default": 50}})

    V = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
         (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    E = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
         (0, 4), (1, 5), (2, 6), (3, 7)]

    def render(self, ctx: Ctx):
        w, h = self.size
        img = F.canvas(w, h)
        d = ImageDraw.Draw(img)
        a = self._audio
        t = ctx.t
        audio = self.config.get("audio", True)
        lvl = a.level if audio and a.ok else 0.5 - 0.5 * math.cos(t * 1.5)
        ax, ay = t * 0.7, t * 0.9
        s = min(w, h) * 0.34 * (0.85 + 0.5 * lvl)
        cx, cy = w / 2, h / 2
        ca, sa = math.cos(ax), math.sin(ax)
        cb, sb = math.cos(ay), math.sin(ay)
        proj = []
        for x, y, z in self.V:
            y, z = y * ca - z * sa, y * sa + z * ca   # rotate X
            x, z = x * cb + z * sb, -x * sb + z * cb  # rotate Y
            proj.append((cx + x * s, cy + y * s, z))
        for i, j in self.E:
            zavg = (proj[i][2] + proj[j][2]) / 2
            g = int(110 + 110 * (zavg + 1.6) / 3.2)   # nearer edges brighter
            d.line([proj[i][:2], proj[j][:2]], fill=max(40, min(255, g)), width=1)
        if HAVE_NP:
            return self._feedback(np.asarray(img, dtype=np.float32))
        return img


class StarfieldApplet(_Viz):
    meta = AppletMeta(key="starfield", name="Starfield", description="Warp stars (beat-reactive)",
                      config_schema={"fps": {"type": "int", "default": 20, "label": "FPS"},
                                     "count": {"type": "int", "default": 90, "label": "Stars"},
                                     "audio": {"type": "bool", "default": False, "label": "Audio reactive"},
                                     "speed": {"type": "int", "default": 100, "label": "Speed %"},
                                     "trails": {**TRAILS, "default": 66}})

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self.config.pop("warp", None)  # old saved configs had a warp option
        self.xs = np.empty(0, dtype=np.float32)
        self.ys = np.empty(0, dtype=np.float32)
        self.zs = np.empty(0, dtype=np.float32)
        self.flags = np.empty(0, dtype=np.bool_)
        self._lt = 0.0

    def _seed(self, n: int) -> None:
        self.xs = np.random.uniform(-1, 1, n).astype(np.float32)
        self.ys = np.random.uniform(-1, 1, n).astype(np.float32)
        self.zs = np.random.uniform(0.05, 1.0, n).astype(np.float32)
        self.flags = np.random.random(n) < 0.7  # True = stays tiny; False = can bloom

    def render(self, ctx: Ctx):
        w, h = self.size
        a = self._audio
        n = max(8, int(self.config.get("count", 90)))
        if len(self.xs) != n:
            self._seed(n)

        dt = max(0.0, min(0.1, ctx.t - self._lt))
        self._lt = ctx.t

        audio = self.config.get("audio", True)
        if audio and a.ok:
            lvl, beat = a.level, a.beat
        else:
            lvl, beat = 0.1, 0.0
        pace = max(0, min(500, int(self.config.get("speed", 100)))) / 100.0
        speed = (0.25 + 1.4 * lvl + 1.8 * beat) * dt * pace

        xs, ys, zs, flags = self.xs, self.ys, self.zs, self.flags
        zs -= speed

        # Give each respawned star its own depth so clusters don't stay clumped.
        reset = zs <= 0.02
        if np.any(reset):
            n_reset = np.count_nonzero(reset)
            xs[reset] = np.random.uniform(-1, 1, n_reset).astype(np.float32)
            ys[reset] = np.random.uniform(-1, 1, n_reset).astype(np.float32)
            zs[reset] = np.random.uniform(0.9, 1.0, n_reset).astype(np.float32)
            flags[reset] = np.random.random(n_reset) < 0.7

        cx, cy = w / 2, h / 2
        scale = min(w, h) * 0.9
        sx = cx + xs / zs * scale
        sy = cy + ys / zs * scale
        g = 255.0 * (1.0 - zs)

        ix = np.floor(sx).astype(np.int32)
        iy = np.floor(sy).astype(np.int32)
        inside = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)

        # Near stars bloom into 2x2 blocks; the rest stay single pixels.
        point_mask = inside & (flags | (zs > 0.4))
        bloom_mask = inside & (~flags) & (zs <= 0.4)

        img = np.zeros((h, w), dtype=np.float32)
        if np.any(point_mask):
            px = ix[point_mask]
            py = iy[point_mask]
            img[py, px] = g[point_mask]

        if np.any(bloom_mask):
            bx = ix[bloom_mask]
            by = iy[bloom_mask]
            bv = g[bloom_mask]
            right = bx + 1 < w
            down = by + 1 < h
            np.maximum.at(img, (by, bx), bv)
            np.maximum.at(img, (by[right], bx[right] + 1), bv[right])
            np.maximum.at(img, (by[down] + 1, bx[down]), bv[down])
            np.maximum.at(img, (by[right & down] + 1, bx[right & down] + 1), bv[right & down])

        return self._feedback(img)
