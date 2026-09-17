"""ASUS ZenVision backend (USB 0b05:8835, 256x64 4bpp).

Wraps the reverse-engineered protocol from the sibling project `zenvision-linux`
(MIT). Transport: vendor interface 0, command channel on interrupt EP 0x03, pixels
on bulk EP 0x07. See that project's PROTOCOL.md for the full description.
"""
from __future__ import annotations

import datetime

import numpy as np
from PIL import Image

from .base import Panel

VID, PID = 0x0B05, 0x8835
IFACE = 0
EP_CMD = 0x03      # interrupt OUT — 512-byte commands
EP_BULK = 0x07     # bulk OUT — 8704-byte framebuffer
EP_REPLY = 0x82    # interrupt IN — 512-byte engine-state replies
FRAME_BYTES = 8704

# Constant 8704-byte framebuffer geometry (page header at bp 0, marker at
# page 16/bp 1, pixel data after bp >= 4). Precomputed once instead of
# rebuilding the scatter indices on every frame (~35 us/frame saved).
_POS = np.arange(FRAME_BYTES)
_BP, _PAGE = _POS & 0x1FF, _POS >> 9
_HEAD_AT = np.flatnonzero(_BP == 0)
_HEAD = _PAGE[_HEAD_AT].astype(np.uint8)
_ONE_AT = np.flatnonzero((_BP == 1) & (_PAGE == 16))
_BODY_POS = np.flatnonzero(_BP >= 4)

# Built-in content commands that hand the panel back to its autonomous engine;
# anything else (battery/sweep/bootanim/speed/clocktime/brightness) is a panel
# setting that does not take over the display.
TAKEOVER_COMMANDS = ("clock", "theme")


def encode(img: Image.Image, width: int = 256, height: int = 64) -> bytes:
    img = img.convert("L")
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)

    arr = np.asarray(img, dtype=np.uint8).reshape(-1) >> 4   # 16384 nibbles
    n = arr.reshape(-1, 4)                                    # (4096, 4)
    data = np.empty(8192, dtype=np.uint8)
    data[0::2] = n[:, 2] | (n[:, 3] << 4)
    data[1::2] = n[:, 0] | (n[:, 1] << 4)

    out = np.zeros(FRAME_BYTES, dtype=np.uint8)
    out[_HEAD_AT] = _HEAD
    out[_ONE_AT] = 1
    out[_BODY_POS[: data.size]] = data
    return out.tobytes()


def _cmd(*head: int) -> bytes:
    b = bytearray(512)
    b[: len(head)] = bytes(head)
    return bytes(b)


def _clamp(value, lo: int, hi: int, label: str) -> int:
    v = int(value)
    if not (lo <= v <= hi):
        raise ValueError(f"{label} out of range: {v} (expected {lo}-{hi})")
    return v


def build_command(name: str, value=None) -> bytes:
    """Encode a PROTOCOL.md v2 command as a 512-byte EP 0x03 buffer."""
    if name == "clock":
        return _cmd(0x30, 0x05, 0x01, _clamp(value, 1, 2, "clock layout"))
    if name == "theme":
        return _cmd(0x30, 0x05, 0x02, 0x00, _clamp(value, 1, 4, "theme"))
    if name == "battery":
        # 30 05 04 00 00 00 <val>: 01 = off, 03 = on (on the clock layouts)
        return _cmd(0x30, 0x05, 0x04, 0, 0, 0, 0x03 if value else 0x01)
    if name == "sweep":
        # 31 02 00 04 = screen sweep off, 31 02 02 03 = on
        return _cmd(0x31, 0x02, 0x02 if value else 0x00, 0x03 if value else 0x04)
    if name == "bootanim":
        # 32 02 00 00 = boot animation off, 32 02 02 02 = on
        return _cmd(0x32, 0x02, 0x02 if value else 0x00, 0x02 if value else 0x00)
    if name == "speed":
        return _cmd(0x33, 0x01, _clamp(value, 1, 3, "speed"))
    if name == "brightness":
        return _cmd(0x35, 0x01, _clamp(value, 0, 255, "brightness"))
    if name == "clocktime":
        # 40 09 <year le u16> <month> <day> <hour> <min> <sec> <format> <weekday>
        now = datetime.datetime.now()
        t = value or {}
        hour = int(t.get("hour", now.hour))  # hour is always stored 24h
        weekday = int(t.get("weekday", (now.weekday() + 1) % 7))  # 0=Sun..6=Sat
        return _cmd(
            0x40, 0x09,
            int(t.get("year", now.year)) & 0xFF,
            (int(t.get("year", now.year)) >> 8) & 0xFF,
            _clamp(t.get("month", now.month), 1, 12, "month"),
            _clamp(t.get("day", now.day), 1, 31, "day"),
            _clamp(hour, 0, 23, "hour"),
            _clamp(t.get("minute", now.minute), 0, 59, "minute"),
            _clamp(t.get("second", now.second), 0, 59, "second"),
            1 if t.get("format", 1) else 0,
            weekday % 7,
        )
    if name == "status":
        return _cmd(0xF1, 0x03)
    raise ValueError(f"unknown command {name!r}")


class ZenVisionPanel(Panel):
    name = "zenvision"
    width = 256
    height = 64

    def __init__(self) -> None:
        self.dev = None
        self._bright = 0xFF
        self._builtin = False  # panel is playing its own content, not host frames
        self._sweep = False  # panel's burn-in screen-sweep is latched on

    def open(self) -> None:
        import usb.core
        import usb.util

        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise RuntimeError("ZenVision (0b05:8835) not found")
        try:
            if self.dev.is_kernel_driver_active(IFACE):
                self.dev.detach_kernel_driver(IFACE)
        except Exception:
            pass
        usb.util.claim_interface(self.dev, IFACE)

    def _c(self, data: bytes) -> None:
        self.dev.write(EP_CMD, data, timeout=3000)

    def _b(self, data: bytes) -> None:
        self.dev.write(EP_BULK, data, timeout=3000)

    def _sweep_off(self) -> None:
        self._c(_cmd(0x31, 0x02, 0x00, 0x04))  # screen sweep off
        self._sweep = False

    def _ensure_sweep_off(self) -> None:
        """One-off sweep-off during pure frame pushes (flag-tracked, no-op normally).

        The burn-in sweep is latched on the panel (e.g. by clock layout 2) and
        its animation would otherwise sweep over streamed frames — a periodic
        stutter with no host involvement.
        """
        if self._sweep:
            self._sweep_off()

    def show_image(self, img: Image.Image, brightness: int = 255) -> None:
        fb = encode(img, self.width, self.height)
        self._c(_cmd(0x30, 0x06, 0x05, 0, 0, 0, 0, 0x01))     # content mode 1 = custom image
        self._b(fb)                                           # pixels — shown immediately, no apply step
        self._sweep_off()                                     # guarantee no sweep over custom content
        if brightness != self._bright:
            self.set_brightness(brightness)
        self._builtin = False

    def begin_stream(self, brightness: int = 255) -> None:
        self._c(_cmd(0x30, 0x06, 0x05, 0, 0, 0, 0, 0x02))     # content mode 2 = custom stream
        self.set_brightness(brightness)
        self._sweep_off()                                     # guarantee no sweep over streamed frames
        self._builtin = False

    def push_frame(self, img: Image.Image) -> None:
        if self._builtin:
            self.begin_stream(self._bright)  # built-in content was playing — retake control
        self._ensure_sweep_off()
        self._b(encode(img, self.width, self.height))

    def set_brightness(self, brightness: int) -> None:
        self._bright = brightness & 0xFF
        self._c(_cmd(0x35, 0x01, self._bright))

    def send_command(self, name: str, value=None) -> None:
        """Send a built-in content / panel-setting command (PROTOCOL.md v2)."""
        data = build_command(name, value)
        self._c(data)
        if name == "sweep":
            self._sweep = bool(value)
        elif name in TAKEOVER_COMMANDS:
            self._builtin = True

    def query_engine(self) -> str | None:
        """Ask what content engine is playing.

        ``F1 03`` triggers a reply on EP 0x82 whose first bytes are ASCII:
        ``01`` clock, ``02`` theme, ``07`` custom image.
        """
        if self.dev is None:
            return None
        try:
            # The reply slot is single-buffered and answers every command — send
            # the query twice: the first read drains the stale reply, the second
            # returns the fresh one for this very F1 03.
            self._c(_cmd(0xF1, 0x03))
            self.dev.read(EP_REPLY, 512, timeout=500)
            self._c(_cmd(0xF1, 0x03))
            raw = bytes(self.dev.read(EP_REPLY, 512, timeout=500))
        except Exception:
            return None
        return raw.rstrip(b"\x00").decode("ascii", errors="replace") or None

    def close(self) -> None:
        if self.dev is not None:
            import usb.util

            try:
                usb.util.release_interface(self.dev, IFACE)
                usb.util.dispose_resources(self.dev)
            except Exception:
                pass
            self.dev = None