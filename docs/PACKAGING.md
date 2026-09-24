# Packaging & releasing

This project ships as a standalone `.deb` attached to GitHub releases. This document
explains what the package contains, how the build works, and how to cut a release.

## What the .deb is

`zenvision-studio_<version>_<arch>.deb` is a **self-contained** package: Python and
every runtime dependency are bundled into `/opt/zenvision-studio/site` at build time
(`pip install --target`), so the only thing required on the target machine is a
working `python3` (>= 3.10). No system packages for pyusb/Pillow/FastAPI etc. are
needed — this is what makes the same package installable on old Ubuntu/Debian
releases whose Python libraries are long frozen.

It installs:

| Path | What it is |
| --- | --- |
| `/opt/zenvision-studio/site/` | the `zvstudio` package + all pip dependencies |
| `/usr/bin/zvstudio` | thin wrapper: puts the bundled site on `PYTHONPATH`, then execs the CLI |
| `/usr/lib/systemd/user/zvstudio.service` | user daemon unit (autostart via `systemctl --user enable --now zvstudio`) |
| `/usr/lib/udev/rules.d/70-zenvision.rules` | USB access for the panel (`uaccess`; filename order matters, see file header) |
| `/usr/share/applications/zenvision-studio-tray.desktop` | tray app menu entry |
| `/etc/xdg/autostart/zenvision-studio-tray.desktop` | KDE-only: tray icon auto-starts at login |
| `/usr/share/icons/hicolor/256x256/apps/zvstudio.png` | app icon |
| `/usr/share/licenses/zenvision-studio/LICENSE` | MIT license |

`postinst` reloads udev rules and re-reads systemd user units on install, so the
panel is immediately accessible and the daemon can be enabled without a reboot.
`prerm`/`postrm` do the reverse on removal: they stop and disable the daemon unit
(`systemctl --user disable --now zvstudio`, reached via `runuser` for every
logged-in user since apt runs them as root) and reload udev/systemd, leaving no
running process or dangling symlink behind.

The tray icon is the one feature with system-library requirements: `pystray` is
bundled, but its AppIndicator backend needs `python3-gi` and
`gir1.2-ayatanaappindicator3-0.1` installed on the host (present by default on
Kubuntu). Without them the tray simply refuses to start with a hint — nothing
else is affected.

## Building locally

```bash
packaging/deb/build-deb.sh          # -> dist/zenvision-studio_<version>_<arch>_<pytag>.deb
```

The artifact is tagged with the interpreter that built it (`_py312`, `_py314`, …);
that is the only Python minor it will run on. `PYTAG=...` overrides the suffix.

Prerequisites: `dpkg-deb`, a Python 3.11+ `python3 -m pip`, and PyPI access (the
build downloads all dependencies into the bundle). Extras are controlled by the
`EXTRAS` env var (comma-separated, empty = none); the default is `tray`
(pystray for the KDE tray icon; numpy is a base dependency). The release `.deb`
is built with that default, so **video playback is not bundled** — the `video`
extra would add imageio + a ~80 MB ffmpeg binary (~30 MB to the download):

```bash
EXTRAS=  packaging/deb/build-deb.sh            # minimal bundle
EXTRAS="video,tray" packaging/deb/build-deb.sh # + video player (imageio)
```

The script stages everything under `dist/_build-deb/`, writes the control files,
and assembles with `dpkg-deb --build --root-owner-group` (all files end up
root-owned, so the package doesn't depend on who built it).

### Caveats

- **The package is effectively arch-specific** even though the bundling is plain
  Python — binary wheels (numpy, Pillow, uvloop, pydantic-core, …) are compiled for
  the build machine's CPU (`dpkg --print-architecture` is stamped into the package).
  Build on the architecture you want to release for (the CI workflow builds on
  `ubuntu-latest` = x86_64/amd64).
- **Wheels are CPython-minor-specific** (uvloop, httptools, pydantic-core, numpy, …):
  an artifact only runs on the exact Python minor it was built with. The release
  workflow builds one per supported distro Python — `py312` (Ubuntu 24.04 LTS) and
  `py314` (Ubuntu/Kubuntu 26.04). Local builds are tagged with your `python3`.
  The `/usr/bin/zvstudio` wrapper checks the host minor and exits with a clear
  message on a mismatch (instead of a cryptic ImportError).
- Each artifact declares `Depends: python3 (>= <major.minor>)` matching the
  interpreter it was built with, so apt refuses to install it on older systems.

## How to release

Everything is automated: pushing a `v*` tag triggers
`.github/workflows/release.yml`, which builds both .debs on `ubuntu-latest`
(x86_64, Python 3.12 + 3.14) and uploads them to a GitHub release for that tag.

1. **Bump the version** in `pyproject.toml` (`version = "0.2.1"`).
2. **Commit and tag**:
   ```bash
   git commit -am "release: v0.2.1"
   git tag v0.2.1
   git push origin main --tags
   ```
3. **Let CI do the rest.** The `release` workflow builds
   `dist/zenvision-studio_0.2.1_amd64_py312.deb` and `..._py314.deb` and creates a
   GitHub release `v0.2.1` (notes auto-generated from merged PRs) with both
   attached. If the release already exists, it just uploads/clobbers the assets.
4. **Sanity-check the installed package** on a clean machine (pick the matching
   Python):
   ```bash
   sudo apt install ./zenvision-studio_0.2.1_amd64_py312.deb   # 24.04 LTS / Python 3.12
   sudo apt install ./zenvision-studio_0.2.1_amd64_py314.deb   # 26.04+ / Python 3.14
   zvstudio daemon            # web UI on http://127.0.0.1:8787
   systemctl --user enable --now zvstudio
   ```
   The udev rule + `uaccess` grant the active graphical user USB access to the
   panel automatically (non-root, matching the 70-zenvision.rules mechanism).

`workflow_dispatch` on the workflow builds the .deb without publishing (a dry-run
for testing the build on CI before tagging).

## Removing the package

apt handles it like any other local package:

```bash
sudo apt remove zenvision-studio        # stop + disable daemon, remove files
sudo apt purge zenvision-studio         # same for this package — your data is untouched
```

`prerm`/`postrm` stop and disable the user daemon (per logged-in user) and reload
udev/systemd, so no process keeps running and no dangling unit symlink stays
behind. Two things are **kept on purpose** when the package is removed:

- **Your data** — config, playlist and uploaded media live under
  `~/.config/zvstudio/`, i.e. in your home directory, not in the package. They
  survive remove/purge (and reinstalls), which is what you want for a personal
  setup.
- **Installed packages** — nothing is auto-removed; `apt autoremove` won't touch
  the bundled site either, because it's all self-contained under
  `/opt/zenvision-studio`. The whole install footprint lives in the paths listed
  in the table above.

## Why not dh-virtualenv / fpm / a PPA?

- **`dh-virtualenv`** would give a cleaner "native" Debian package, but it requires
  a `debian/` directory and the tool on every build host, and the resulting package
  is still a bundled venv — the `--target` + wrapper approach is the same idea with
  zero extra build tooling.
- **`fpm`** is an extra Ruby dependency and has known quirks around ownership and
  compression defaults; `dpkg-deb` is already everywhere.
- **A PPA** would offer apt updates, but requires Ubuntu hosting, signing keys, and
  per-version maintenance; GitHub releases with a pinned-URL install are enough for
  this project's cadence.