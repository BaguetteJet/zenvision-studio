# Writing an applet

An applet renders one frame per tick: a PIL `"L"` (8-bit grayscale) image at the
panel's native size (256×64). The [compositor](../zvstudio/core/compositor.py)
decides which applet is active, paces it at `min(daemon fps, applet fps)` and hands
the frame to the panel backend. Everything above the backend is plain Pillow —
only `core/device/` knows the USB format.

A complete runnable example lives in
[`examples/sample_applet.py`](../examples/sample_applet.py) (a bouncing dot with a
config schema and a plugin entry point).

## Minimal applet

```python
from zvstudio.core.applets.base import Applet, AppletMeta, Ctx
from zvstudio.core import frame as F

class HelloApplet(Applet):
    meta = AppletMeta(key="hello", name="Hello", description="says hi")

    def render(self, ctx: Ctx):
        img = F.canvas(*self.size)
        F.text(img, (self.size[0] // 2, 32), "hello :)", size=22, anchor="mm")
        return img
```

## The `Applet` interface

Subclass `Applet` and implement **`render(ctx) -> Image`**. The context gives you:

| Field | Meaning |
| --- | --- |
| `ctx.t` | Seconds since this applet became active — **animate from this**. |
| `ctx.frame` | Frames rendered since active (a counter, not a clock). |
| `ctx.size` | `(width, height)` — same as `self.size`. |

Optional hooks:

| Hook | Purpose |
| --- | --- |
| `fps` *(property)* | Desired rate; defaults to `config["fps"]` or 10. The compositor caps it at the daemon's global fps. |
| `wants_focus()` | Return `True` to preempt the playlist while active (e.g. `nowplaying` when a track starts). |
| `on_start()` / `on_stop()` | Called on transitions into/out of this applet. |
| `meta` | Class-level `AppletMeta(key, name, description, config_schema)`. |

**Animate from `ctx.t`, never from `ctx.frame` or a per-render counter.** The daemon
may cap the rate or the USB push may slow a tick down; a time-based animation keeps
its speed either way. Sequence players index frames by `int(ctx.t * self.fps)`.

## Configuration

Declare options in `meta.config_schema` so the web UI and CLI can expose them
generically. `self.config` merges the declared defaults with user overrides:

```python
class BounceApplet(Applet):
    meta = AppletMeta(
        key="bounce",
        name="Bounce",
        description="A dot bouncing around the panel",
        config_schema={
            "fps":    {"type": "int",  "default": 30, "label": "FPS"},
            "speed":  {"type": "int",  "default": 90, "label": "px/s"},
            "radius": {"type": "int",  "default": 4,  "label": "Dot radius"},
        },
    )

    def render(self, ctx: Ctx):
        speed = float(self.config["speed"])
        ...
```

* Field types: `bool` (checkbox), `int` (number input), `str`/`path`/`color`
  (text input). Each spec may also set `label` and `default`.
* Always declare `"fps"` in the schema if you want it adjustable from the UI.
* Config is per-applet: the UI sends it when pinning, playlists store it per scene.

## Drawing helpers (`zvstudio.core.frame`)

| Helper | Purpose |
| --- | --- |
| `canvas(w, h)` | New `"L"` image (defaults to 256×64). |
| `text(img, xy, s, size=16, fill=255, anchor="lm")` | Draw text (with emoji support). |
| `text_width(s, size)` | Measure a string. |
| `render_text(s, size, fill=255)` | Render a string to a strip — cache it, then scroll it. |
| `scroll(strip, offset, dest, x=0, y=0, gap=24)` | Blit a strip at a scroll offset. |
| `sparkline(values, w, h, fill=255)` | Plot a mini graph. |
| `bar(value, w, h, fill=255, frame=90)` | Progress/value bar with a frame. |
| `font(size)` / `cjk_font(size)` | Cached fonts (CJK/katakana for the Matrix effect). |

## Register it

**Built-in:** drop the class in `zvstudio/core/applets/` and add it to `BUILTIN`
in [`core/registry.py`](../zvstudio/core/registry.py).

**Third-party:** ship it in your own package and register an entry point — no core
edit needed. The entry-point *name* is the applet key used by the registry, the web
UI and `zvstudio show`:

```toml
# pyproject.toml
[project.entry-points."zvstudio.applets"]
bounce = "your_package.bounce:BounceApplet"
```

```bash
pip install -e .        # then the applet shows up in the UI automatically
```

## Keep `render()` cheap

`render()` runs every frame, so a slow applet costs battery and drops frames.

* Cache anything static: render text strips once, rasterize glyphs once, keep
  `lru_cache`-style helpers (see how `matrix` and `text` do it).
* No I/O, network or subprocess calls per frame — poll them, or move fetching to a
  background thread and let `render()` read the last result.
* Prefer NumPy only where it pays off; `core/audio.py` already degrades when NumPy
  or `parec` is missing, so guard optional deps the same way.

## Test it without hardware

Everything runs under the mock backend, and `tests/test_fps.py` drives every applet
through the real compositor loop and asserts its measured rate:

```bash
ZVSTUDIO_BACKEND=mock zvstudio daemon     # watch your applet in the browser
ruff check .
pytest tests/test_fps.py -q
.venv/bin/python tests/profile_applets.py  # per-applet render-cost benchmark
```

## Examples

* [`examples/sample_applet.py`](../examples/sample_applet.py) — bouncing dot with
  config schema and entry point.
* [`examples/tarpediem_bumper.py`](../examples/tarpediem_bumper.py) — renders the
  project logo to half-block ASCII.
* The built-ins in [`core/applets/`](../zvstudio/core/applets/) — `clock`,
  `sysmon`, `nowplaying`, `viz.py`/`fx.py`/`geo.py` visualisers, `layout.py`.
