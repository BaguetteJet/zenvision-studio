# Installation

Requires Python 3.10 or newer

Choose method:

1. [Kubuntu / Ubuntu / Debian](#kubuntu--ubuntu--debian-recommended) *(recommended)*
2. [Installation Script](#installation-script) *(other Linux distros)*
3. [Manual Installation](#from-source)

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

Remove it any time with `sudo apt remove zenvision-studio` (daemon is stopped and disabled, your `~/.config/zvstudio/` data is kept). How the package is built and released: [PACKAGING.md](docs/PACKAGING.md).

## Installation Script

Install ZenVision Studio directly from source. This is a good option for development and other Linux distributions. There is no performance difference compared to the packaged version.

Run install script:
```bash
./install.sh
```

**Enable** and start the daemon:

```bash
systemctl --user enable --now zvstudio
```

The **KDE tray** auto-starts at your next login.

The script performs all required setup steps automatically. To undo script use `./install.sh --uninstall`.

## Manual Installation

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


**Enable** and start the daemon:

```bash
systemctl --user enable --now zvstudio
```

The **KDE tray** auto-starts at your next login.