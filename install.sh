#!/usr/bin/env bash
# Install from a source checkout (no .deb needed).
#
#   ./install.sh
#
# Creates a venv, installs the package with extras, installs the udev rule
# (needs sudo), and generates the systemd user unit + KDE autostart entry
# with the *actual* project paths baked in — no assumptions about where the
# repo lives. Re-running is safe: it updates everything in place.
#
# Overrides:
#   VENV=/path/to/venv ./install.sh      # venv location (default: ./.venv)
#   EXTRAS=audio ./install.sh            # pip extras (default: audio,video,tray)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-$ROOT/.venv}"
BIN="$VENV/bin/zvstudio"
EXTRAS="${EXTRAS:-audio,video,tray}"
UDEV_SRC="$ROOT/udev/70-zenvision.rules"

# ---------------------------------------------------------------------------
# 1. Python venv + package
# ---------------------------------------------------------------------------
echo "==> venv: $VENV (extras: $EXTRAS)"
if [ ! -x "$BIN" ]; then
    # --system-site-packages so the tray can import the system 'gi' bindings
    python3 -m venv --system-site-packages "$VENV"
fi
(cd "$ROOT" && "$VENV/bin/pip" install -q -U -e ".[$EXTRAS]")

# ---------------------------------------------------------------------------
# 2. udev rule (root) — non-root USB access to the panel
# ---------------------------------------------------------------------------
if command -v sudo >/dev/null 2>&1; then
    sudo cp "$UDEV_SRC" /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=usb
else
    echo "!! no sudo found — install the udev rule manually:"
    echo "   sudo cp $UDEV_SRC /etc/udev/rules.d/"
    echo "   sudo udevadm control --reload-rules && sudo udevadm trigger"
fi

# ---------------------------------------------------------------------------
# 3. systemd user unit — daemon at login, with the real binary path
# ---------------------------------------------------------------------------
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
sed "s|^ExecStart=.*|ExecStart=$BIN daemon --host 127.0.0.1 --port 8787|" \
    "$ROOT/systemd/zvstudio.service" >"$UNIT_DIR/zvstudio.service"
systemctl --user daemon-reload
systemctl --user enable --now zvstudio

# ---------------------------------------------------------------------------
# 4. KDE tray — autostart entry + menu icon
# ---------------------------------------------------------------------------
AUTOSTART_DIR="$HOME/.config/autostart"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$AUTOSTART_DIR" "$ICON_DIR"
sed -e "s|^Exec=.*|Exec=$BIN tray|" -e '/^#/d' \
    "$ROOT/systemd/zvstudio-tray.desktop" >"$AUTOSTART_DIR/zvstudio-tray.desktop"
cp "$ROOT/zvstudio/web/logo.png" "$ICON_DIR/zvstudio.png"

# ---------------------------------------------------------------------------
# 5. System deps check for the tray (non-fatal)
# ---------------------------------------------------------------------------
if ! python3 -c "import gi; gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import AyatanaAppIndicator3" >/dev/null 2>&1; then
    echo "!! tray needs system packages (KDE uses AppIndicator/SNI):"
    echo "   sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1"
fi

# ---------------------------------------------------------------------------
# done
# ---------------------------------------------------------------------------
echo
echo "==> installed."
echo "    web UI:      http://127.0.0.1:8787  (daemon already running)"
echo "    tray:        appears at your next login (or: $BIN tray)"
echo "    no hardware? ZVSTUDIO_BACKEND=mock $BIN daemon"