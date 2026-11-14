# Summit OS 2.0: plan

Status: **2.0 alpha 2** installs to a drive and updates over the air from this branch (`summit-2`), so the
rest of 2.0 is developed on installed systems. Built by `build/v2/build-live.sh`: 1.1 GB live image; the
installed system has about 1,040 packages (Summit 1.21 had 1,178) and no installer, live-session helpers or
compiler. Tested in a virtual machine (install to an empty USB drive, start from it, sign in). On the 2014
iMac, alpha 1 reached the desktop but had no sound and the Magic Mouse did not work; cause not yet known.
Nothing here changes Summit 1.x; the `main` branch and its updates carry on as before.

Alpha 2 uses the ordinary disk layout (one writable system partition), not the read-only A/B design below.
Moving to that design will need one more fresh install. Until then:
- Debian's kernel package is held, because the Wi-Fi and Magic Mouse drivers are built for one exact kernel
  and the system has no compiler to rebuild them. Kernel updates will come with Summit updates.
- Whole-disk encryption is switched off in the installer; home-folder encryption is still to come.
- Secure Boot is not supported (the boot loader is unsigned). Macs don't use it; PCs need it turned off.

Build it: `sudo build/v2/build-live.sh [workdir]` on a Debian or Ubuntu machine. The package list with the
reason for every entry is `build/v2/packages.txt`; what the finished image contains is `build/v2/image-manifest.txt`.

## What 2.0 is

Summit 1.x is Ubuntu 24.04 with Summit laid over it. Summit 2.0 is an operating system image that Summit
assembles itself from an empty disk, on the Linux kernel, taking patched packages from Debian.

| Goal | How 2.0 meets it |
|---|---|
| No bloat | The image starts empty. A package is in it only because Summit uses it, and the list is in this repository with a reason per entry. No snap, no vendor telemetry, no services that are not used. |
| Tight security | The system is read-only. Updates replace the whole system with a signed image and can roll back. Inbound network traffic is refused unless a Sharing switch is on. Apps are sandboxed. |
| Privacy for all users | Each account's home folder is encrypted with that account's password, so users of one computer cannot read each other's files and a stolen disk is unreadable. The OS itself contacts only the update server, and every outbound connection it can make is listed in `docs/NETWORK.md`. |

## Decisions made

- **Base: Debian stable** (13, "trixie"). Community-run, long security support.
- **Fresh install.** 2.0 has a different disk layout, so 1.x cannot be upgraded in place.
- **Audience: public.** A download other people can install, not only the 2014 iMac.

## Design

### Disk layout

| Partition | Contents | Notes |
|---|---|---|
| EFI | Boot loader, kernels | |
| System A | Read-only system image | The running system |
| System B | Read-only system image | The previous or the next system |
| Data | `/var`, `/home`, apps | Home folders individually encrypted |

The system partitions are never written while running. Settings that must change (`/etc`) live on Data as
a thin layer over the image, so a reset to factory settings is deleting that layer.

### Updates

1. A build server produces a system image and signs it. The private key never enters this repository.
2. The computer downloads the image, checks the signature against the public key built into the running
   system, and writes it to the slot that is not in use.
3. The next start uses the new slot. If it fails to reach the desktop, the boot loader returns to the old one.

There is no package manager changing the system on the user's computer. Drivers that 1.x compiled on the
machine (Wi-Fi, Magic Mouse) are compiled when the image is built.

### Apps

Flatpak only, installed per user or system-wide under Data. The App Store stays; its Ubuntu `.deb`
section is removed.

### Encryption

Per-account encrypted home folders, unlocked by the login password. Whole-disk encryption with a
passphrase at power-on is offered in the installer but is not the default: on a Mac with a Bluetooth
keyboard nothing can be typed that early.

### Network defaults

- Firewall refuses all inbound connections. Each Sharing switch opens exactly the ports it needs.
- Wi-Fi uses a random hardware address per network.
- No crash reporting, no usage statistics, no captive-portal pings to a vendor, no location lookups
  unless Night Shift's automatic schedule is turned on.

## Phases

| Phase | Result | Can be tested |
|---|---|---|
| 0 | Debian's servers reachable from the build workspace | n/a |
| 1 | **2.0 alpha 1:** live USB image on the Debian base with the Summit desktop. Runs from a USB stick without touching the SSD. | VM, then the iMac from USB |
| 2 | Installer with the A/B layout and encrypted homes | VM |
| 3 | Signed image updates with roll-back; no package manager on the installed system | VM |
| 4 | Network defaults, sandbox review, `docs/NETWORK.md` audit | VM |
| 5 | Public release: wider hardware testing, build server that rebuilds weekly for security fixes, download page | other machines |

## What phase 1 settled

- **Kernel:** Debian's stable kernel (6.12). Summit's Magic Mouse driver compiles against it unchanged.
- **Wi-Fi:** the Broadcom driver compiles at image build time and ships as a ready module.
- **No compiler in the image:** both drivers are built during the image build, then the compiler, kernel
  headers and build tools are removed; the build fails if any remain.
- **Dock and compositor:** Debian 13 carries both, the compositor in the same version Summit 1.x builds itself.
- **Not in Debian 13:** the keyboard-and-mouse sharing program (Barrier) and the old password-prompt
  agent. The prompt agent is replaced; keyboard-and-mouse sharing is missing from alpha 1.
- **Still as in 1.x:** the alpha has no firewall rules, no installer and no image updates; those are phases 2 to 4.

## Known risks, as written before phase 1

- **Kernel.** Debian stable ships an older kernel than Summit 1.x uses. Summit's Magic Mouse scrolling
  driver was written against the newer one and must be ported or the newer kernel taken from Debian backports.
- **Wi-Fi.** The iMac's Broadcom card needs Debian's non-free driver package, built into the image.
- **Summit's own binaries** (the compositor build, the window helper) were compiled against Ubuntu's
  libraries and must be rebuilt.
- **Dock.** Whether Debian stable still carries the Dock program Summit uses has not been checked; if
  not, Summit builds it from source.
- **Security upkeep.** A read-only image only gets fixes when a new image is built. Phase 5's weekly
  rebuild is what keeps 2.0 as safe as 1.x is today; it needs somewhere to run (GitHub Actions is the
  natural place) and a signing key that someone holds.

## Open decisions

- Who holds the image signing key, and where the weekly build runs.
- Whether 1.x keeps receiving features once 2.0 alpha exists, or only fixes.
