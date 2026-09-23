# CLI reference

`zvstudio` has two modes:

* **Direct** — `play` / `anim` open the panel themselves, push frames and exit (no daemon).
* **Client** — every other verb is a thin HTTP client to the running daemon, and mirrors
  the API the [web UI](http://127.0.0.1:8787) uses.

```bash
zvstudio daemon                  # own the panel, serve the web UI
zvstudio <verb> [options]        # control the running daemon
```

Client verbs accept `--url` **before** the verb (default `http://127.0.0.1:8787`):

```bash
zvstudio --url http://192.168.1.20:8787 status
```

## daemon

```bash
zvstudio daemon [--host 127.0.0.1] [--port 8787] [--backend zenvision|mock|auto]
```

Owns the panel and the render loop, and serves the web UI, REST API and `/ws/preview`
mirror on the given address. Backend resolution: `--backend` > `ZVSTUDIO_BACKEND` env >
`auto` (real panel if attached, otherwise mock). No hardware? Use the mock backend and
watch the live preview in the browser:

```bash
ZVSTUDIO_BACKEND=mock zvstudio daemon
```

Run it at login with the systemd user service — set up by the `.deb` and `install.sh`,
or manually as described in [INSTALL.md](INSTALL.md#manual-installation).

## Client commands

| Command | Description |
| --- | --- |
| `zvstudio status` | Full daemon status as JSON (current applet, playlist, brightness, fps…). |
| `zvstudio show <applet>` | Pin one applet, e.g. `zvstudio show plasma`. Beats the rotation until the playlist changes or you resume. |
| `zvstudio brightness <value>` | Hardware brightness, `0`–`255` decimal or `0x` hex (`zvstudio brightness 0x80`). |
| `zvstudio power on\|off` | Panel on/off. `off` also turns the burn-in screen sweep off (the MyASUS pairing). |
| `zvstudio command <name> [value]` | Built-in content and panel settings — see the table below. |
| `zvstudio tray` | System-tray icon — see [System tray](#system-tray). |

Pinning an applet, changing the playlist, or `zvstudio command clock|theme` takes the
panel back from its built-in engine and returns to streaming your own frames.

## Built-in content (`zvstudio command`)

These commands hand the panel back to its own engine: the compositor pauses, the live
preview is hidden (frames are generated on the panel, not the host), and pinning an
applet returns to streaming. Wire format: [PROTOCOL.md](PROTOCOL.md#command-channel-ep-0x03).

| Name | Value | Effect |
| --- | --- | --- |
| `clock` | `1`–`2` | Built-in clock layout. Layout 2 also enables the screen sweep. |
| `theme` | `1`–`4` | Built-in theme. |
| `battery` | `on` / `off` | Battery icon on the clock layouts. |
| `sweep` | `on` / `off` | Burn-in-protection sweep over static content. |
| `bootanim` | `on` / `off` | Lid-close boot animation. |
| `speed` | `1`–`3` | Speed of the built-in content. |
| `brightness` | `0`–`255` | Hardware brightness (same as the `brightness` verb). |
| `clocktime` | *(none)* / `now` | Set the panel's clock to the current local time. |
| `status` | — | Query what the panel engine is playing (`clock`, `theme` or custom image). |

Booleans accept `on`/`off` (also `true`/`false`, `yes`/`no`). Examples:

```bash
zvstudio command theme 2         # panel's built-in theme
zvstudio command clock 1         # built-in clock layout
zvstudio command bootanim off    # disable the lid-close animation
zvstudio command status          # what's playing on the panel
```

## Direct commands (no daemon)

```bash
zvstudio play picture.png [--white] [--bright 0xNN] [--hold SECONDS]
zvstudio anim frames/ [--fps 20] [--bright 0xNN]
```

* `play` shows one image (auto-scaled/grayscaled by the panel backend) and exits.
  `--white` shows a blank white test pattern instead of a file; `--hold` keeps the
  process alive for a few seconds before closing.
* `anim` loops a folder of `.png` / `.jpg` frames until `Ctrl-C`.

> [!NOTE]
> The panel's USB interface is exclusive: stop the daemon before using direct
> commands (`systemctl --user stop zvstudio`), or it will fail to claim the device.
> Under `ZVSTUDIO_BACKEND=mock` there is no conflict.

## System tray

```bash
zvstudio tray                    # needs `zvstudio daemon` running
```

A small KDE/Plasma tray icon controls the running daemon: open the web UI, toggle
power, play built-in content, pin an applet, set brightness.

The `.deb` bundles `pystray` and auto-starts the tray at login. From a source
checkout it needs the `tray` extra *and* the system AppIndicator bindings — see
[INSTALL.md](INSTALL.md#system-tray).

## See also

* [APPLETS.md](APPLETS.md) — write your own applet
* [PROTOCOL.md](PROTOCOL.md) — the USB wire format
* [INSTALL.md](INSTALL.md) — installation and tray setup
