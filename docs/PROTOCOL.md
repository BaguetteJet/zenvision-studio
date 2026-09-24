# ZenVision USB protocol

> [!NOTE]
> This is **version 2** of these notes. The built-in content command set was added from
> the [zenvision-protocol-research](https://github.com/BaguetteJet/zenvision-protocol-research)
> repo — USB captures of the MyASUS app, cross-checked against the live panel.
> Anything still uncertain is flagged below.

Reverse-engineered notes for driving the lid OLED of the **ASUS Zenbook 14X OLED
Space Edition (UX5401ZAS)** from Linux. Written from scratch as interoperability
documentation — it describes *how to talk to the device*, not anyone's source
code. Command meanings were confirmed from USB captures of the MyASUS app on
Windows (USBPcap) and cross-checked against a live panel.

If you have a different ASUS model with a lid OLED ("ZenVision" / "APanel"), the
framing may differ; contributions welcome.

## The device

| | |
|---|---|
| USB ID | `0b05:8835` (iProduct `M480 BULK`, iManufacturer `Nuvoton`) |
| Controller | Nuvoton M480 (Cortex-M4F) MCU driving an SSD1362-class panel |
| Panel | 256 × 64 px, monochrome, **4-bit grayscale** (16 levels) |
| Speed | USB 2.0 High Speed |

The device exposes **two USB interfaces**:

* **Interface 0 — vendor-specific (class 0xFF).** This is the one we use:
  * `0x03` — interrupt **OUT**, 512 bytes — **command channel**
  * `0x07` — **bulk OUT**, 512 bytes — **image data**
  * `0x82` — interrupt **IN**, 512 bytes — **engine-state replies** (below)
* **Interface 1 — HID.** Used by the vendor software for the *keyboard* RGB/LED
  and layout queries, **not** for the OLED. Ignore it for display purposes.

At rest, when no host is talking to it, the MCU autonomously plays built-in
content (themes, clock) from internal flash — this is what you see during POST
and on a fresh boot. To show your own content you take over interface 0.

## Engine state (EP 0x82)

Every command on EP 0x03 is answered on EP 0x82 with a 512-byte buffer whose
first bytes are ASCII. Only the **last** reply is buffered — a new command
overwrites the previous one, so the driver drains before querying.

| Reply | Content engine |
|---|---|
| `01` | clock layout |
| `02` | built-in theme |
| `07` | custom image content |

The explicit query `F1 03` also triggers a reply, so you can ask *what is
playing right now* at any time (`zvstudio command status`).

## Command channel (EP 0x03)

Commands are **512-byte buffers**, sent as a single interrupt-OUT transfer. Only
the first few bytes are meaningful; the rest are zero. The first byte is an ASCII
digit acting as an opcode group.

| Command (first bytes) | Meaning |
|---|---|
| `30 05 01 <mode>` | Show a built-in **clock layout** (1–2); the panel keeps time itself |
| `30 05 02 00 <theme>` | Play a built-in **theme** (1–4) |
| `30 05 04 00 00 00 <val>` | **Battery icon** off (`01`) / on (`03`) on the clock layouts; a bare `30 05 04` powers the panel off (not exposed by the driver) |
| `30 06 05 00 00 00 00 <mode>` | Set **content mode**: `01` custom image (filter "none"), `02` custom stream, `03` news ticker |
| `31 02 00 04` / `31 02 02 03` | **Screen sweep** off / on (burn-in-protection bars over static content) |
| `32 02 00 00` / `32 02 02 02` | **Boot animation** (lid-close) off / on |
| `33 01 <speed>` | Speed of built-in content (1 slow … 3 fast) |
| `35 01 <val>` | **Brightness**: `00`-`FF` 0-255, default levels: `0f`, `4f`, `bc`|
| `40 09 <datetime>` | Set the panel **clock** (byte layout below) |
| `F1 03` | Query the content engine (reply on EP 0x82, see above) |

> [!WARNING]
> The `30 05 01/02…` commands select **built-in** content and hand the panel back
> to its autonomous loop — anything you pushed before is replaced. To show your
> own pixels again, set the content mode and send a framebuffer
> (e.g. `zvstudio play picture.png`).

### Reinterpretations from the captures

Two commands work differently than earlier revisions assumed:

* `30 06 05 00 00 00 00 01` / `02` select **content mode** (1 = image, 2 =
  stream), rather than "begin static image" / "enter streaming mode".
* `31 02` is the **screen sweep** toggle; brightness is a separate command
  (`35 01`). No commit/apply step exists — the content-mode command plus the
  bulk transfer itself display the frame.

### `40 09` — clock layout

| Byte(s) | Field | Encoding | Example |
|---|---|---|---|
| 0–1 | command | `40 09` | `40 09` |
| 2–3 | year | little-endian u16 | `EA 07` = 2026 |
| 4 | month | 1–12 | `09` |
| 5 | day | 1–31 | `0F` |
| 6 | hour | 0–23, always stored 24h | `0E` |
| 7 | minute | 0–59 | `1E` |
| 8 | second | 0–59 | `00` |
| 9 | format | `01` = 24h, `00` = 12h | `01` |
| 10 | weekday | 0 = Sunday … 6 = Saturday | `02` |

## Image data (EP 0x07)

One frame is a single **8704-byte** (`0x2200`) bulk transfer. Layout: **17 packets
of 512 bytes**. Each packet's first byte is its index (0–16); packet 16 also has a
`01` in its second byte as an end marker; bytes 2–3 are reserved (0); bytes 4–511
carry payload (508 bytes/packet). The payload, concatenated across packets, is the
**8192-byte 4bpp framebuffer**.

* **Static content**: a single chunk per display. (MyASUS text templates.)
* **Streamed content**: chunks streamed continuously while active; filters are
  live animations in the pixel data. (MyASUS custom theme, personal label.)

### Encoding an image to the 8192-byte framebuffer

1. **Grayscale, 4-bit, row-major.** For each pixel (y outer 0..63, x inner 0..255):
   `gray = (R + G + B) / 3`, then keep the top nibble `nib = gray >> 4` (0..15).
   This yields 16384 nibbles, one per pixel.

2. **Pack two pixels per byte, with a pair swap.** For each group of 4 source
   pixels (`s = 4k`):

   ```
   data[2k]     = nib[s+2] | (nib[s+3] << 4)
   data[2k + 1] = nib[s]   | (nib[s+1] << 4)
   ```

   i.e. the low nibble is the earlier pixel, and the two output bytes of each
   4-pixel group are emitted in swapped order (a quirk of the panel's addressing).
   Result: 8192 bytes.

3. **Wrap in the 17×512 packet framing** described above to get the 8704 bytes.

See `encode()` in [`zvstudio/core/device/zenvision.py`](../zvstudio/core/device/zenvision.py)
for a reference implementation (the standalone sibling driver is
[zenvision-linux](https://github.com/tarpediem/zenvision-linux)).

## Showing a static image

```
EP 0x03  <-  30 06 05 00 00 00 00 01      (content mode 1 = custom image)
EP 0x07  <-  <8704-byte frame>            (pixels — shown immediately)
EP 0x03  <-  31 02 00 04                  (screen sweep off, optional)
```

There is **no commit/apply command** — the frame appears as soon as the bulk
transfer lands. Re-sending the mode + frame pair causes a brief redraw flicker.

The screen sweep (`31 02`) is a burn-in-protection animation that MyASUS pairs
with static content; this driver leaves it **off** by default and only sends the
command when requested (e.g. `zvstudio command sweep on`).

## Playing an animation (flicker-free)

Enter streaming content mode once, then push frames bulk-only:

```
EP 0x03  <-  30 06 05 00 00 00 00 02      (content mode 2 = custom stream)
EP 0x03  <-  35 01 <val>                  (brightness, optional)
loop:
    EP 0x07  <-  <8704-byte frame>        (just the bulk transfer)
    sleep ~20 ms                          (the vendor software caps ~50 fps)
```

No per-frame begin/apply ⇒ no blanking between frames.

## Brightness

`35 01 <val>` sets the brightness on a 0–255 byte scale. The named defaults seen
in the MyASUS captures are `0f` (dim), `4f` (mid), `bc` (bright). The CLI
accepts any byte via `--bright N` (decimal or `0x` hex, defaulting to `4f`) or
`zvstudio brightness N` against the daemon. Tune by eye.

## Built-in content

MyASUS drives the built-in content with these sequences:

* **Theme**: speed → theme
* **Clock layout 1**: battery icon → clock 1 → speed → datetime
* **Clock layout 2**: screen sweep on → clock 2 → speed → datetime

`zvstudio command theme|clock|speed|bootanim` implements these directly.

## Settings sequence / recovery

Any settings change in the MyASUS Exclusives settings menu triggers the following
seven-command burst, with just one value changed. Every field is resent at its
current value:

```
30 05 04 00 00 00 <val>   power on/off
31 02 00 04               screen sweep off
40 09 <time> ...          datetime, format, weekday
32 02 <a> <b>             boot animation on/off
35 01 <val>               brightness level
33 01 <speed>             speed
30 05 02 00 <theme>       theme
```

If an unrecognised command is sent, the screen goes black and won't even show the
lid animation. To recover, replay the settings sequence.

## Notes / open questions

* The status endpoint `0x82` replies to **every** command with the current engine
  state (single-slot buffer), not just to `F1 03`.
* HID feature reports on interface 1 (`56 A0 …` and `5c …`) drive the keyboard
  backlight/LED, not the OLED.
* Power: the panel is **not** software power-gated — it is alive and firmware-driven
  at boot. You only need to take over interface 0; nothing in ACPI/WMI needs poking.
* Content mode 3 ("news ticker") and the corresponding `F1 03` reply are still to
  be confirmed on hardware.
