# Summit OS

A macOS-style desktop for a 2014 iMac, built on Ubuntu 24.04 LTS. This repository is both the
**update channel** (every iMac running Summit checks it for updates) and the **source** for building the ISO.

## Layout
| Path | What it is |
|---|---|
| `update.json` | Current version, build number, release notes, packages to add/remove |
| `overlay/` | Every Summit file, laid out like the system root (`overlay/usr/local/bin/...` → `/usr/local/bin/...`) |
| `removed.txt` | Files to delete from installed systems |
| `hooks/post-install.sh` | Runs as root after each update |
| `hooks/user.sh` | Runs once per user in their desktop session after each update |
| `tools/publish.sh` | Bump the version, commit and push an update |
| `tools/install-updater.sh` | Adds updates to an existing Summit 1.2x install |
| `build/` | Package list, diversions and `build-iso.sh` to build the ISO from scratch |
| `design/` | Generators for icons, wallpapers and window buttons |
| `build/src/` | Source for compiled helpers shipped in `overlay/` (the GTK module that hides menu-bar underlines) |

## How updates work
1. A change is made under `overlay/`, then `tools/publish.sh "what changed"` bumps the version and pushes.
2. Each iMac's `summit-update` timer sees the new commit, downloads that exact commit, backs up every file it
   replaces, installs the new files, refreshes caches and runs the hooks. If anything fails it restores the backup.
3. Signed-in desktops refresh in place (menu bar, dock, Spotlight, styles) and show what changed.

**Settings → Software Update** offers *Check Now*, *Install updates automatically* (every 6 hours) and
*Live testing* (every 2 minutes, installs every new commit), plus *Roll Back*.
From a terminal: `summit-update status`, `sudo summit-update check | install | rollback`, `summit-update log`.

## Adding updates to an existing install
```
curl -fsSL https://raw.githubusercontent.com/LeaseGeese/summitos/main/tools/install-updater.sh | sudo bash
```
