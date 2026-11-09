#!/bin/bash
# Runs as root after an update's files are installed (every update, so keep it idempotent).
# Environment: SUMMIT_FROM_BUILD, SUMMIT_TO_BUILD, SUMMIT_LIVE (1 in the USB live session)
set -u
systemctl enable --now summit-update.timer >/dev/null 2>&1 || true
systemctl --global enable summit-update-watch.path >/dev/null 2>&1 || true
# make sure the drive starts on a Mac through the generic "EFI Boot" path (fixes 1.0–1.21 installs)
[ "${SUMMIT_LIVE:-0}" = 1 ] || /usr/local/sbin/summit-efi-sync || true
exit 0
