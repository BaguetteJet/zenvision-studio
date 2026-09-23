# Installation

Requires Python 3.10 or newer.

Choose a method:

1. [Kubuntu / Ubuntu / Debian](#kubuntu--ubuntu--debian-recommended) *(recommended)*
2. [Installation Script](#installation-script) *(other Linux distributions)*
3. [Manual Installation](#manual-installation)

## Kubuntu / Ubuntu / Debian (recommended)

> The tray requires two system packages, which ship with **Kubuntu** by default. For Ubuntu and Debian:    
> `sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1`

Download the latest `.deb` from the [Releases](https://github.com/baguettejet/zenvision-studio/releases) page and install it:

```bash
sudo apt install ./zenvision-studio_*.deb
```

The package bundles all required dependencies and installs:

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

Remove it any time with `sudo apt remove zenvision-studio` (the daemon is stopped and disabled, your `~/.config/zvstudio/` data is kept). How the package is built and released: [PACKAGING.md](PACKAGING.md).

## Installation Script

Install ZenVision Studio directly from a source checkout. This is a good option for development and other Linux distributions; there is no performance difference compared to the packaged version.

Run the install script:

```bash
./install.sh
```

The script performs all required setup automatically — venv, udev rule, systemd user service (enabled and started), and KDE tray autostart. To undo it, use `./install.sh --uninstall`.

The **KDE tray** auto-starts at your next login (or run `zvstudio tray`).

## Manual Installation

Create a virtual environment and install the package:

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

Install and start the daemon (the `sed` bakes the venv path into the unit):

```bash
mkdir -p ~/.config/systemd/user
sed "s|^ExecStart=.*|ExecStart=$PWD/.venv/bin/zvstudio daemon|" \
    systemd/zvstudio.service > ~/.config/systemd/user/zvstudio.service
systemctl --user daemon-reload
systemctl --user enable --now zvstudio
```

### System tray

The tray needs the `pystray` extra *and* the system `gi` bindings, so create the
venv with `--system-site-packages` (and install the system packages if you are
not on Kubuntu):

```bash
python -m venv --system-site-packages .venv   # when (re)creating the venv
pip install -e ".[audio,video,tray]"
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1
# Arch/CachyOS: sudo pacman -S --needed python-gobject libayatana-appindicator
cp systemd/zvstudio-tray.desktop ~/.config/autostart/   # auto-start on login
```
