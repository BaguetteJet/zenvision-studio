# ZenVision Studio · *BaguetteJet EDITION*

**Lid display controls on Linux for the ASUS Zenbook 14X Space Edition**

> [!IMPORTANT]   
> This project is a custom version of [zenvision-studio](https://github.com/tarpediem/zenvision-studio) by [tarpediem](https://github.com/tarpediem), focused on performance, personalization, and Kubuntu support.

![The ZenVision lid OLED running zenvision-studio](docs/starfield.gif)

## Introduciton

The Zenbook 14X OLED Space Edition (UX5401ZAS) has a small 256×64 monochrome OLED display built into the lid. ASUS only provides MyASUS Windows software for it.

This project brings support to Linux through a lightweight daemon and web UI, featuring live applets, audio-reactive visualisers, a timeline animation editor, and drag-and-drop screen layouts.

**This version** of zenvision studio combines the original [zenvision-linux](https://github.com/tarpediem/zenvision-linux) driver with additional commands discovered through my own [protocol research](https://github.com/BaguetteJet/zenvision-protocol-research), along with performance improvements and personal customizations. Packaging for Kubuntu/Ubuntu/Debian instead of Arch/CachyOS.

> [!WARNING]   
> **OLED Burn-In Risk**   
> Displaying static elements for an extended amount of time will cause permanent pixel degradation. 

## Visualisers

![effects gallery](docs/gallery.png)

Plasma · tunnel · kaleidoscope · Lissajous · moiré · metaballs · ripple · fire ·
katakana **Matrix** rain · starfield · wireframe cube · triangles — plus a VU-meter
spectrum and an audio oscilloscope. All grayscale-graded with **MilkDrop-style
trails**, an **Auto-VJ** that cycles them, and a **Layout-VJ** that switches
multi-effect compositions **in tempo**.

## The web UI

| Dashboard | Zone layout editor | Timeline animation editor |
|---|---|---|
| ![dashboard](docs/ui-dashboard.png) | ![layout](docs/ui-layout.png) | ![timeline](docs/ui-timeline.png) |

Live mirror of the panel, brightness/power, per-applet settings, a drag-and-drop
**zone editor** (split the panel into regions), and a stylus-friendly **timeline editor**:
draw keyframes, then **tween** between them with per-keyframe **easing** (linear /
ease-in / out / in-out), **hold** durations and a seamless **loop tween** — the editor
interpolates the in-between frames and streams the result to the panel. Reachable from
your phone over the LAN / Tailscale.

## Features

- **Applets**: clock, system monitor (CPU/RAM/temp + sparkline), now-playing
  (MPRIS marquee + progress), text marquee, weather (Open-Meteo), media player
  (image / GIF / video).
- **Audio-reactive visualisers** (see above) with trails, Auto-VJ and a
  tempo-synced Layout-VJ.
- **Built-in content**: hand the panel back to its own engine — clock layouts,
  themes, battery icon, screen sweep, boot animation, speed, hardware brightness
  and clock setting, all from the web UI (no live preview: frames are generated
  on the panel).
- **Web UI**: live panel mirror, per-applet settings, zone layout editor, in-browser
  **timeline** animation editor (keyframes/tween/easing/loop), drag-and-drop upload —
  works from a phone.
- **Compositor**: rotates a playlist of scenes; an applet can *preempt* (now-playing
  pops in on a track change). Flicker-free streaming.
- **Cross-desktop**: a headless daemon + a browser page — nothing depends on KDE/GNOME.
- **Hardware-free dev**: a `mock` backend renders to a preview/PNG, so the whole stack
  (and CI) runs with no device attached.
- **Pluggable**: third-party applets register via the `zvstudio.applets` entry point.

## Installation

### Kubuntu / Ubuntu / Debian (recommended)

Download the latest `.deb` from the [Releases](https://github.com/baguettejet/zenvision-studio/releases) page and install it:

```bash
sudo apt install ./zenvision-studio_*.deb
```

**Requires** Python 3.10 or newer

The package is self-contained and bundles all required dependencies. It installs:

* ZenVision Studio daemon
* Web UI
* systemd user service
* udev rule for non-root USB access
* Desktop menu entry
* KDE tray icon

**Enable** and start the daemon:

```bash
systemctl --user enable --now zvstudio
```

The **KDE tray** auto-starts at your next login.

Remove it any time with `sudo apt remove zenvision-studio` (daemon is stopped and disabled, your `~/.config/zvstudio/` data is kept). How the package is built and released: [docs/PACKAGING.md](docs/PACKAGING.md).

### From source

Alternatively, you can install ZenVision Studio directly from source. This a good option for development and other Linux distributions. There is no performance difference compared to the packaged version.

Run install script:
```bash
./install.sh
```
The script performs all required setup steps automatically.

#### Manual setup

Create python environment and install the package:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[audio,video]"
```

Non-root USB access:

```bash
sudo cp udev/70-zenvision.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

The VU-meter / visualisers read system audio levels via `parec` (PipeWire/PulseAudio).

## Run

```bash
# Start the daemon + web UI (real panel auto-detected, else mock)
zvstudio daemon                      # open http://127.0.0.1:8787

# No hardware? Force the mock backend and watch the live preview in the browser:
ZVSTUDIO_BACKEND=mock zvstudio daemon

# CLI
zvstudio status
zvstudio show plasma
zvstudio brightness 0x80
zvstudio power off
zvstudio command theme 2        # panel's built-in theme
zvstudio command clock 1        # built-in clock layout
zvstudio command status         # what's playing on the panel

# Or skip the daemon for a one-shot:
zvstudio play picture.png
zvstudio anim frames/ --fps 20
```

Run at login (systemd user service, runs as your user so now-playing/MPRIS works):

```bash
cp systemd/zvstudio.service ~/.config/systemd/user/
systemctl --user enable --now zvstudio
```

(When installed from the `.deb`, the unit is already in place — just
`systemctl --user enable --now zvstudio`.)

### System-tray icon (KDE / Plasma)

A small tray icon controls the running daemon — open the web UI, toggle power,
play built-in content, pin an applet, set brightness:

```bash
zvstudio tray                                  # needs `zvstudio daemon` running
```

From the `.deb`, `pystray` is already bundled and KDE auto-starts the tray at
login (`/etc/xdg/autostart/`). It just needs two system packages, which Kubuntu
ships by default:

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1
```

From source, `pystray` comes from the `tray` extra — and the venv must see the
system `gi` module, so create it with `--system-site-packages`:

```bash
pip install -e ".[tray]"
python -m venv --system-site-packages .venv   # if recreating the venv
# Arch/CachyOS: sudo pacman -S --needed python-gobject libayatana-appindicator
cp systemd/zvstudio-tray.desktop ~/.config/autostart/   # auto-start on login
```

## Write an applet

An applet returns one 256×64 grayscale frame per tick:

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

Register it via a `[project.entry-points."zvstudio.applets"]` entry and it shows up in
the UI automatically. Full example in [`examples/`](examples/).

## Architecture

```
device/      Panel backends — zenvision (USB) + mock (no hardware)
applets/     Applet plugins (clock, sysmon, viz/fx/geo, …) — render(ctx) -> 256x64 'L'
compositor   Render loop: playlist + preempt + built-in pause, flicker-free streaming
daemon/api   FastAPI: REST + live preview + zone layout + draw upload
web/         Vanilla-JS dashboard, zone editor, frame editor (no build step)
```

## Roadmap

- ✅ Update and optimize starfield applet (my fav)
- ✅ Optimize display process to use less resources
- ✅ Optimize remaining applets
- ✅ Correct date/time on lid close animation
- ✅ Implement default built-in themes
- ✅ Package for Kubuntu/Ubuntu/Debian (`.deb` GitHub Releases - see [docs/PACKAGING.md](docs/PACKAGING.md))
- Fix default animation playing briefly on suspend

## Credits

Originally created by [tarpediem](https://github.com/tarpediem), who created the project based on the reverse-engineered protocol documented in [zenvision-linux](https://github.com/tarpediem/zenvision-linux). This project is unofficial and is not affiliated with or endorsed by ASUS. 

This fork is maintained and updated by [BaguetteJet](https://github.com/BaguetteJet).

## License

[MIT](LICENSE)
