"""Benchmark every applet's render cost (standalone — not collected by pytest).

Run::

    .venv/bin/python tests/profile_applets.py [--daemon-fps N]

Method
------
Each applet is rendered ``FRAMES`` times (40), paced at ``rate = min(daemon_fps,
applet_fps)`` — exactly what the compositor schedules (compositor.py ``_loop``)
— so ``ms/frame`` is the real on-panel cost. One warm-up render runs first
(grids, glyph caches, child applets…).

CPU is reported twice: at the applet's *declared* fps (its theoretical max) and
at the *daemon hard cap* — even when declared is below the cap, so the ceiling
column shows what the applet would cost if driven flat-out by the daemon.

Note: ``cycle``/``layoutvj`` declare the *max* fps of their children, so raising
a visualiser's fps propagates to them (the compositor honours it, capped).
"""
import argparse
import time

from zvstudio.core.applets.base import Ctx
from zvstudio.core.registry import all_applets

SIZE = (256, 64)
FRAMES = 40  # render budget per applet (measurement only, not a playback setting)

HEADER = ("{:<12} {:>9} {:>7} {:>7} {:>9} {:>8} {:>8} {:>10} {:>11}"
          .format("applet", "declared", "daemon", "rate", "ms/frame",
                  "max fps", "sustains", "CPU@decl", "CPU@daemon"))
ROW = "{:<12} {:>9.1f} {:>7.0f} {:>7.1f} {:>9.2f} {:>8.0f} {:>8} {:>9.1f}% {:>10.1f}%"


def profile(daemon_fps: float) -> None:
    rows = []
    for key, klass in sorted(all_applets().items()):
        ap = klass(size=SIZE)
        try:
            ap.render(Ctx(t=0.0, frame=0, size=SIZE))  # warm-up: caches / children
        except Exception:
            pass
        declared = max(0.5, ap.fps)
        rate = min(daemon_fps, declared)  # what the compositor actually requests
        t0 = time.perf_counter()
        n = 0
        for i in range(FRAMES):
            try:
                ap.render(Ctx(t=i / rate, frame=i, size=SIZE))
                n += 1
            except Exception:
                pass
        dt = time.perf_counter() - t0
        ms = dt / max(1, n) * 1000.0
        max_fps = 1000.0 / ms
        rows.append((key, declared, ms, max_fps, rate))

    rows.sort(key=lambda r: r[2])
    print(HEADER)
    print("-" * len(HEADER))
    for key, declared, ms, max_fps, rate in rows:
        sustain = "yes" if max_fps >= rate else "NO"
        cpu_decl = ms * declared / 10.0   # % of one core at the declared fps
        cpu_daemon = ms * daemon_fps / 10.0  # % of one core at the hard cap
        print(ROW.format(key, declared, daemon_fps, rate, ms, max_fps, sustain,
                         cpu_decl, cpu_daemon))
    print("-" * len(HEADER))
    print(f"declared = applet's own fps  ·  daemon = the hard cap ({daemon_fps:.0f}, config.py)")
    print(f"rate = min(daemon, declared), the rate the compositor actually drives "
          f"·  ms/frame measured at that rate ({FRAMES} renders)")
    print("max fps = 1000 / ms/frame  ·  sustains = max fps >= rate")
    print("CPU@decl = % of one core at the declared fps  ·  CPU@daemon = % at the hard cap "
          "(always the ceiling, even when declared < cap).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daemon-fps", type=float, default=60.0,
                        help="daemon global fps cap (default 60, as in config.py)")
    args = parser.parse_args()
    profile(args.daemon_fps)