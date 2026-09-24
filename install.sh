#!/usr/bin/env bash
# Install / uninstall from a source checkout (no .deb needed).
#
#   ./install.sh                # install
#   ./install.sh --uninstall    # reverse: venv, udev rule, unit, tray files
#   ./install.sh --uninstall -y # skip the confirmation prompt
#
# Install: creates a venv, installs the package with extras, installs the udev
# rule (needs sudo), and generates the systemd user unit + KDE autostart entry
# with the *actual* project paths baked in — no assumptions about where the
# repo lives. Re-running is safe: it updates everything in place.
#
# Uninstall only removes what this script installed (checked against the repo
# files); your data under ~/.config/zvstudio/ is always kept.
#
# Overrides:
#   VENV=/path/to/venv ./install.sh      # venv location (default: ./.venv)
#   EXTRAS=video ./install.sh            # pip extras (default: video,tray)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-$ROOT/.venv}"
BIN="$VENV/bin/zvstudio"
EXTRAS="${EXTRAS:-video,tray}"
UDEV_SRC="$ROOT/udev/70-zenvision.rules"

UNINSTALL=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --uninstall | -u) UNINSTALL=1 ;;
        --yes | -y) FORCE=1 ;;
        *)
            echo "usage: $0 [--uninstall] [-y]" >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# UNINSTALL
# ---------------------------------------------------------------------------
if [ "$UNINSTALL" = 1 ]; then
    if [ "$FORCE" = 0 ]; then
        read -r -p "Remove venv, udev rule, systemd unit, tray autostart + icon? [y/N] " ans
        case "$ans" in
            y | Y | yes | YES) ;;
            *) echo "aborted"; exit 0 ;;
        esac
    fi

    # venv — only if it's actually a zvstudio venv
    if [ -x "$BIN" ]; then
        rm -rf "$VENV"
        echo "==> removed $VENV"
    else
        echo "!! $VENV has no zvstudio binary — leaving it alone"
    fi

    # udev rule — only if it's still the file we installed
    if [ -f /etc/udev/rules.d/70-zenvision.rules ] && [ -r "$UDEV_SRC" ] \
        && cmp -s /etc/udev/rules.d/70-zenvision.rules "$UDEV_SRC"; then
        if command -v sudo >/dev/null 2>&1; then
            sudo rm -f /etc/udev/rules.d/70-zenvision.rules
            sudo udevadm control --reload-rules
            sudo udevadm trigger --subsystem-match=usb
            echo "==> removed /etc/udev/rules.d/70-zenvision.rules"
        else
            echo "!! no sudo found — remove manually:"
            echo "   sudo rm /etc/udev/rules.d/70-zenvision.rules"
            echo "   sudo udevadm control --reload-rules && sudo udevadm trigger"
        fi
    else
        echo "!! /etc/udev/rules.d/70-zenvision.rules absent or modified by hand — not touching it"
    fi

    # systemd user unit
    systemctl --user disable --now zvstudio 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/zvstudio.service"
    systemctl --user daemon-reload
    echo "==> removed ~/.config/systemd/user/zvstudio.service"

    # tray autostart + icon
    rm -f "$HOME/.config/autostart/zvstudio-tray.desktop" \
        "$HOME/.local/share/icons/hicolor/256x256/apps/zvstudio.png"
    echo "==> removed tray autostart entry + icon"

    echo "==> uninstalled. your data under ~/.config/zvstudio/ was kept."
    exit 0
fi

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