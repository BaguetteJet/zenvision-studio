"""FPS behaviour tests: each applet must render at min(daemon_fps, its own fps).

The compositor is the single scheduler (compositor.py ``_loop``): the daemon's
global fps is a hard ceiling and 0.5 fps is the floor, so an applet's declared
fps is honoured only below that. These tests drive each applet through the real
compositor loop (mock backend) and measure the achieved render rate.
"""
import time

import pytest

from zvstudio.config import DEFAULT
from zvstudio.core.compositor import Compositor, Scene
from zvstudio.core.device.mock import MockPanel
from zvstudio.core.registry import all_applets

SIZE = (256, 64)
DAEMON_CAP = float(DEFAULT["fps"])  # the global ceiling, set in config.py


class _SlowPanel(MockPanel):
    """Mock panel whose push_frame simulates real USB transfer latency (~9ms)."""

    def __init__(self) -> None:
        super().__init__()
        self.push_latency = 0.0094

    def push_frame(self, img) -> None:
        time.sleep(self.push_latency)
        super().push_frame(img)


def render_rate(applet, daemon_fps: float, secs: float) -> tuple[float, float, float]:
    """Run the applet under the real compositor; return (measured fps, applet fps, actual_fps)."""
    stamps: list[float] = []
    orig = type(applet).render

    def counting(ctx):
        stamps.append(time.monotonic())
        return orig(applet, ctx)

    applet.render = counting
    comp = Compositor(MockPanel(), fps=daemon_fps)
    comp.set_playlist([Scene(applet, duration=999)])
    comp.start()
    time.sleep(secs)
    comp.stop()
    final_fps = applet.fps  # post-build: meta applets (cycle/layoutvj) build children on start
    actual = comp.actual_fps
    if len(stamps) < 2:
        return 0.0, final_fps, actual
    # first-to-last stamp window: immune to start/stop boundary effects
    return (len(stamps) - 1) / (stamps[-1] - stamps[0]), final_fps, actual


@pytest.mark.parametrize("key", sorted(all_applets().keys()))
def test_render_rate_matches_declared_fps(key):
    applet = all_applets()[key](size=SIZE)
    secs = 1.6 if max(0.5, applet.fps) <= 2.0 else 1.0
    rate, final_fps, actual = render_rate(applet, daemon_fps=DAEMON_CAP, secs=secs)
    declared = max(0.5, final_fps)
    expected = min(DAEMON_CAP, declared)
    assert abs(rate - expected) <= max(0.6, 0.2 * expected), (
        f"{key}: declared {declared:.1f} fps, daemon cap {DAEMON_CAP:.0f}, measured {rate:.1f} fps"
    )
    # compositor's own measured rate (what the web UI reports) must agree
    assert abs(actual - expected) <= max(0.6, 0.2 * expected), (
        f"{key}: declared {declared:.1f} fps, daemon cap {DAEMON_CAP:.0f}, "
        f"compositor.actual_fps {actual:.1f}"
    )


def test_daemon_fps_is_the_ceiling():
    plasma = all_applets()["plasma"](size=SIZE)  # declares 30 fps
    rate, _, _ = render_rate(plasma, daemon_fps=8.0, secs=1.0)
    assert abs(rate - 8.0) <= 1.0, f"expected ~8 fps (daemon cap), measured {rate:.1f}"


def test_daemon_does_not_raise_applet_fps():
    clock = all_applets()["clock"](size=SIZE)  # declares 2 fps
    rate, _, _ = render_rate(clock, daemon_fps=30.0, secs=1.0)
    assert abs(rate - 2.0) <= 0.6, f"expected ~2 fps (applet's own), measured {rate:.1f}"


def test_slow_panel_push_does_not_slow_the_schedule():
    # Regression: the wait between frames used to be computed from the pre-render
    # time, so every frame took period + push_latency (real USB ~9ms) — declared
    # 60fps showed ~37fps. The wait must compensate for the render/push time.
    starfield = all_applets()["starfield"](size=SIZE, config={"fps": 60})
    stamps: list[float] = []
    orig = type(starfield).render

    def counting(ctx):
        stamps.append(time.monotonic())
        return orig(starfield, ctx)

    starfield.render = counting
    comp = Compositor(_SlowPanel(), fps=60.0)
    comp.set_playlist([Scene(starfield, duration=999)])
    comp.start()
    time.sleep(1.5)
    comp.stop()
    rate = (len(stamps) - 1) / (stamps[-1] - stamps[0])
    assert abs(rate - 60.0) <= 10.0, f"expected ~60 fps despite 9.4ms pushes, got {rate:.1f}"


def test_software_brightness_dims_frames():
    # The panel firmware ignores the hardware brightness command on UX5401ZAS,
    # so the compositor scales frames in software. 255 -> full, 128 -> half.
    from PIL import Image

    from zvstudio.core.applets.frames import FramesApplet

    white = Image.new("L", SIZE, 255)
    ap = FramesApplet(size=SIZE, frames=[white])
    comp = Compositor(MockPanel(), fps=20.0)
    comp.set_playlist([Scene(ap, duration=999)])
    comp.set_brightness(128)
    comp.start()
    time.sleep(0.2)
    comp.stop()
    assert comp.preview().getpixel((0, 0)) == 128, "brightness 128 should halve a 255 frame"