#!/usr/bin/env bash
# Build a standalone .deb for zenvision-studio.
#
# Strategy: Python + every runtime dependency is bundled (pip install --target)
# under /opt/zenvision-studio/site; /usr/bin/zvstudio is a thin wrapper that
# puts that directory on PYTHONPATH and execs the entry point. The package only
# depends on a system python3 (>= 3.10) — no Debian package for any Python dep
# is needed, which is what makes it viable on old Ubuntu/Debian releases.
#
# Extras to bundle are controlled by EXTRAS (comma-separated, empty = none).
# Default "audio,tray" matches the release .deb (adds numpy for the VU-meter
# and pystray for the system-tray icon).
#
# Output: dist/zenvision-studio_<version>_<arch>.deb
#
# Prereqs: dpkg-deb, python3 >= 3.11 (for pip) with network access to PyPI.
set -euo pipefail

cd "$(dirname "$0")/../.."  # repo root

command -v dpkg-deb >/dev/null || { echo "error: dpkg-deb not found" >&2; exit 1; }

VERSION=$(python3 -c "import re; print(re.search(r'^version = \"([^\"]+)\"', open('pyproject.toml').read(), re.M).group(1))")
ARCH=$(dpkg --print-architecture)
MAINTAINER="${MAINTAINER:-Igor Kochanski <baguette.jet@gmail.com>}"
EXTRAS="${EXTRAS:-audio,tray}"
DEB="dist/zenvision-studio_${VERSION}_${ARCH}.deb"

echo "==> zenvision-studio ${VERSION} (arch: ${ARCH}, extras: ${EXTRAS:-none})"

# ---------------------------------------------------------------------------
# Stage the payload
# ---------------------------------------------------------------------------
STAGE="dist/_build-deb"
SITE="$STAGE/opt/zenvision-studio/site"
rm -rf "$STAGE"
mkdir -p "$SITE" "$STAGE/DEBIAN"

echo "==> bundling python deps into $SITE (this needs PyPI access)"
if [[ -n "$EXTRAS" ]]; then
  python3 -m pip install --target "$SITE" --no-compile --no-input ".[$EXTRAS]"
else
  python3 -m pip install --target "$SITE" --no-compile --no-input "."
fi

# ---------------------------------------------------------------------------
# /usr/bin wrapper — keeps the bundled site on PYTHONPATH, nothing else
# ---------------------------------------------------------------------------
install -d "$STAGE/usr/bin"
cat >"$STAGE/usr/bin/zvstudio" <<'EOF'
#!/bin/sh
# Bundled dependencies live in /opt/zenvision-studio/site.
exec env PYTHONPATH=/opt/zenvision-studio/site python3 -c "import sys; from zvstudio.cli import main; sys.exit(main(sys.argv[1:]))" "$@"
EOF
chmod 0755 "$STAGE/usr/bin/zvstudio"

# ---------------------------------------------------------------------------
# systemd user unit (points at the /usr/bin wrapper, not ~/.local/bin)
# ---------------------------------------------------------------------------
install -d "$STAGE/usr/lib/systemd/user"
sed 's|ExecStart=.*|ExecStart=/usr/bin/zvstudio daemon --host 127.0.0.1 --port 8787|' \
  systemd/zvstudio.service >"$STAGE/usr/lib/systemd/user/zvstudio.service"

# ---------------------------------------------------------------------------
# udev rule (must sort before 73-seat-late.rules, see file header)
# ---------------------------------------------------------------------------
install -d "$STAGE/usr/lib/udev/rules.d"
cp udev/70-zenvision.rules "$STAGE/usr/lib/udev/rules.d/"

# ---------------------------------------------------------------------------
# desktop entry + tray icon
# ---------------------------------------------------------------------------
install -d "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/256x256/apps"
cp systemd/zvstudio-tray.desktop "$STAGE/usr/share/applications/"
cp zvstudio/web/logo.png "$STAGE/usr/share/icons/hicolor/256x256/apps/zvstudio.png"

# ---------------------------------------------------------------------------
# KDE autostart — tray icon appears at login (next session). OnlyShowIn=KDE,
# so GNOME/other desktops just get the menu entry, not an auto-started tray.
# ---------------------------------------------------------------------------
install -d "$STAGE/etc/xdg/autostart"
cat >"$STAGE/etc/xdg/autostart/zenvision-studio-tray.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=zenvision-studio tray
Comment=System-tray control for the ASUS ZenVision lid OLED
Exec=zvstudio tray
Icon=zvstudio
Terminal=false
Categories=Utility;
OnlyShowIn=KDE;
X-KDE-autostart-after=panel
EOF

# ---------------------------------------------------------------------------
# license
# ---------------------------------------------------------------------------
install -d "$STAGE/usr/share/licenses/zenvision-studio"
cp LICENSE "$STAGE/usr/share/licenses/zenvision-studio/"

# ---------------------------------------------------------------------------
# DEBIAN control files
# ---------------------------------------------------------------------------
cat >"$STAGE/DEBIAN/control" <<EOF
Package: zenvision-studio
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: $MAINTAINER
Depends: python3 (>= 3.10)
Homepage: https://github.com/tarpediem/zenvision-studio
Description: Drive the ASUS ZenVision lid OLED from Linux.
  A headless daemon plus web UI that renders live applets, audio-reactive
  visualisers, multi-zone layouts and timeline animations on the 256x64
  monochrome lid OLED, then pushes grayscale frames over USB.
  Python dependencies are bundled under /opt/zenvision-studio, so only a
  working python3 (>= 3.10) is required.
EOF

cat >"$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger --subsystem-match=usb 2>/dev/null || true
systemctl --user daemon-reload 2>/dev/null || true
exit 0
EOF
chmod 0755 "$STAGE/DEBIAN/postinst"

cat >"$STAGE/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
# Only on real removal — never on upgrade, or the unit would stay disabled
# after reinstalling.
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
  # apt runs us as root, but the daemon is a systemd *user* unit: poke every
  # logged-in user's user-manager directly.
  for u in $(loginctl list-users --no-legend 2>/dev/null | awk '{print $2}'); do
    uid=$(id -u "$u" 2>/dev/null) || continue
    [ -d "/run/user/$uid" ] || continue
    runuser -u "$u" -- env XDG_RUNTIME_DIR="/run/user/$uid" \
      systemctl --user disable --now zvstudio 2>/dev/null || true
  done
fi
exit 0
EOF
chmod 0755 "$STAGE/DEBIAN/prerm"

cat >"$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
systemctl --user daemon-reload 2>/dev/null || true
udevadm control --reload-rules 2>/dev/null || true
exit 0
EOF
chmod 0755 "$STAGE/DEBIAN/postrm"

# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
mkdir -p dist
dpkg-deb --build --root-owner-group "$STAGE" "$DEB"
rm -rf "$STAGE"

echo "==> built $DEB"
dpkg-deb -I "$DEB" | sed -n '1,12p'