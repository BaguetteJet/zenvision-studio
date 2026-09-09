"""The compositor owns the panel and runs the render loop in a background thread.

It rotates through a playlist of scenes, lets a "focus-wanting" applet preempt
the rotation (e.g. now-playing when media starts), and pushes frames using the
panel's flicker-free streaming mode.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from PIL import Image

from .applets.base import Applet, Ctx
from .device.base import Panel

# Precomputed point() lookup tables for beat-flash (one per brightness step).
_FLASH_LUTS = [bytes(min(255, v + add) for v in range(256)) for add in range(141)]


@dataclass
class Scene:
    applet: Applet
    duration: float = 10.0  # seconds before rotating to the next scene


class Compositor:
    def __init__(self, panel: Panel, fps: float = 20.0) -> None:
        self.panel = panel
        self.fps = fps
        self.brightness = 255
        self.enabled = True
        self.beat_flash = False

        self._scenes: list[Scene] = []
        self._preempt: list[Applet] = []
        self._pinned: Applet | None = None  # manual override (no rotation)

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()  # set to interrupt the disabled-idle wait early
        self._cur: Applet | None = None
        self._cur_start = 0.0
        self._cur_frame = 0
        self._preview = Image.new("L", panel.size, 0)
        self._last_pushed: bytes | None = None  # raw pixel bytes of the last frame sent
        self._black_sent = False  # whether the current off period already pushed black
        self._black = Image.new("L", panel.size, 0)  # reused when disabled

    def preview(self) -> Image.Image:
        """Last frame rendered (mirrors the panel; works on any backend)."""
        with self._lock:
            return self._preview.copy()

    def current_key(self) -> str | None:
        ap = self._cur
        return ap.meta.key if ap is not None else None

    # --- configuration ---------------------------------------------------
    def set_playlist(self, scenes: list[Scene]) -> None:
        with self._lock:
            self._scenes = list(scenes)
            self._pinned = None
            self._reset_current(None)
        self._wake.set()

    def set_preempt(self, applets: list[Applet]) -> None:
        with self._lock:
            self._preempt = list(applets)
        self._wake.set()

    def pin(self, applet: Applet | None) -> None:
        with self._lock:
            self._pinned = applet
            self._reset_current(None)
        self._wake.set()

    def set_brightness(self, value: int) -> None:
        self.brightness = max(0, min(255, int(value)))
        try:
            self.panel.set_brightness(self.brightness)
        except Exception:
            pass

    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)
        if self.enabled:
            self._black_sent = False
            self._wake.set()

    def set_beat_flash(self, on: bool) -> None:
        on = bool(on)
        if on == self.beat_flash:
            return  # idempotent: avoid double acquire()/release() on repeat toggles
        from .audio import AudioLevel
        if on:
            AudioLevel.get().acquire()
        else:
            AudioLevel.get().release()
        self.beat_flash = on

    def _flash(self, img):
        """Brighten the whole frame on each audio beat (global beat-flash mode)."""
        try:
            from .audio import AudioLevel
            b = AudioLevel.get().beat
        except Exception:
            return img
        if b <= 0.02:
            return img
        add = int(140 * min(1.0, b))
        if add <= 0:
            return img
        return img.point(_FLASH_LUTS[add])

    # --- lifecycle -------------------------------------------------------
    def start(self) -> None:
        if self._thread:
            return
        self.panel.begin_stream(self.brightness)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="compositor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self.beat_flash:
            self.set_beat_flash(False)
        if self._cur:
            try:
                self._cur.on_stop()
            except Exception:
                pass

    # --- internals -------------------------------------------------------
    def _reset_current(self, applet: Applet | None) -> bool:
        """Switch to ``applet`` if it differs from the current one; return True on change."""
        if self._cur is applet:
            return False
        if self._cur:
            try:
                self._cur.on_stop()
            except Exception:
                pass
        self._cur = applet
        self._cur_start = time.monotonic()
        self._cur_frame = 0
        if applet:
            try:
                applet.on_start()
            except Exception:
                pass
        return True

    def _pick(self, now: float, scene_idx: list[int]) -> Applet | None:
        # 1) an explicit manual pin wins — a user choice overrides auto-preempt
        if self._pinned is not None:
            return self._pinned
        # 2) a preempting applet grabs focus during normal rotation (e.g. now-playing)
        for ap in self._preempt:
            try:
                if ap.wants_focus():
                    return ap
            except Exception:
                continue
        # 3) playlist rotation
        if not self._scenes:
            return None
        i = scene_idx[0] % len(self._scenes)
        scene = self._scenes[i]
        if self._cur is scene.applet and (now - self._cur_start) >= scene.duration:
            scene_idx[0] = (i + 1) % len(self._scenes)
            return self._scenes[scene_idx[0]].applet
        return scene.applet

    def _loop(self) -> None:
        scene_idx = [0]
        next_render = 0.0  # when the active applet's next frame is due
        while not self._stop.is_set():
            t0 = time.monotonic()
            if not self.enabled:
                if not self._black_sent:
                    try:
                        self.panel.push_frame(self._black)
                    except Exception:
                        pass
                    with self._lock:
                        self._preview = self._black
                    self._last_pushed = None  # force a real push next time we re-enable
                    self._black_sent = True
                self._wake.wait(timeout=1.0)
                self._wake.clear()
                continue
            with self._lock:
                nxt = self._pick(t0, scene_idx)
                if self._reset_current(nxt):
                    next_render = 0.0  # draw a newly-active applet immediately
                cur = self._cur
            if cur is None:
                # Nothing to show; poll slowly so a preempt can still grab focus.
                self._wake.wait(timeout=0.5)
                self._wake.clear()
                continue
            if t0 >= next_render:
                ctx = Ctx(t=t0 - self._cur_start, frame=self._cur_frame, size=self.panel.size)
                try:
                    img = cur.render(ctx)
                    if img.mode != "L":
                        img = img.convert("L")
                    if self.beat_flash:
                        img = self._flash(img)
                    raw = img.tobytes()
                    if raw != self._last_pushed:
                        self.panel.push_frame(img)
                        self._last_pushed = raw
                    with self._lock:
                        self._preview = img
                except Exception:
                    pass
                self._cur_frame += 1
                # Each applet declares its own fps; the daemon fps is the ceiling.
                period = 1.0 / min(self.fps, max(0.5, cur.fps))
                next_render = t0 + period
            # Re-check the pick (rotation / preempt) at least 4x/s; control calls
            # wake the wait early via self._wake.
            dt = min(next_render, t0 + 0.25) - t0
            if dt > 0:
                self._wake.wait(timeout=dt)
                self._wake.clear()