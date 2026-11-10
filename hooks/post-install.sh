#!/bin/bash
# Runs as root after an update's files are installed (every update, so keep it idempotent).
# Environment: SUMMIT_FROM_BUILD, SUMMIT_TO_BUILD, SUMMIT_LIVE (1 in the USB live session)
set -u
systemctl enable --now summit-update.timer >/dev/null 2>&1 || true
systemctl --global enable summit-update-watch.path >/dev/null 2>&1 || true
# the update timer: every half hour, plus every 2 minutes in Live testing mode (1.25.0; was always 2 minutes).
# The timer is not restarted: it picks the change up from the reload, and a restart would fire it at once.
LIVE_D=/etc/systemd/system/summit-update.timer.d; LIVE_T='[Timer]\nOnUnitActiveSec=2min\nAccuracySec=15s\n'
if python3 -c 'import json,sys; sys.exit(0 if json.load(open("/etc/summit/update.json")).get("live") else 1)' 2>/dev/null; then
  if [ "$(cat $LIVE_D/live.conf 2>/dev/null)" != "$(printf "$LIVE_T")" ]; then
    mkdir -p $LIVE_D; printf "$LIVE_T" > $LIVE_D/live.conf; systemctl daemon-reload >/dev/null 2>&1 || true
  fi
elif [ -f $LIVE_D/live.conf ]; then
  rm -f $LIVE_D/live.conf; systemctl daemon-reload >/dev/null 2>&1 || true
fi
# performance tuning at every start (CPU and GPU clock floors on older Intel chips)
systemctl enable summit-tune.service >/dev/null 2>&1 || true
systemctl start summit-tune.service >/dev/null 2>&1 || true
# the startup disk turned out to be an SSD: the app preloader only wastes memory there
/usr/local/lib/summitos/root-is-rotational || systemctl stop preload.service >/dev/null 2>&1 || true
# fully preemptible kernel: the desktop stays responsive while something heavy runs (applies after restart)
if [ "${SUMMIT_LIVE:-0}" != 1 ] && [ -f /boot/grub/grub.cfg ] && ! grep -q "preempt=full" /boot/grub/grub.cfg; then
  update-grub >/dev/null 2>&1 || true
fi
# Magic Mouse driver with USB-C Magic Mouse support (Linux 6.16 backport), rebuilt automatically for new kernels
MM=summit-magicmouse; MMV=6.16
if [ "${SUMMIT_LIVE:-0}" != 1 ] && [ -d /usr/src/$MM-$MMV ] && command -v dkms >/dev/null; then
  if ! dkms status -m $MM -v $MMV -k "$(uname -r)" 2>/dev/null | grep -q installed; then
    dkms status -m $MM -v $MMV 2>/dev/null | grep -q . || dkms add -m $MM -v $MMV >/dev/null 2>&1
    if dkms install -m $MM -v $MMV >/dev/null 2>&1; then
      modprobe -r hid_magicmouse 2>/dev/null; modprobe hid_magicmouse 2>/dev/null || true
    fi
  fi
fi
# Magic Mouse options (/usr/lib/modprobe.d/summit-magicmouse.conf) for a driver that is already loaded
for kv in emulate_3button=N scroll_acceleration=Y; do
  f=/sys/module/hid_magicmouse/parameters/${kv%%=*}; [ -w "$f" ] && echo "${kv#*=}" > "$f" 2>/dev/null || true
done
# Bluetooth: quicker reconnects for mice, keyboards and trackpads (see bluetooth-setup)
if [ "$(/usr/local/lib/summitos/bluetooth-setup 2>/dev/null)" = changed ]; then
  systemctl try-restart bluetooth.service >/dev/null 2>&1 || true
fi
# touch surfaces readable for gestures (applies to devices already connected too)
udevadm control --reload >/dev/null 2>&1 || true
udevadm trigger --action=change --subsystem-match=input >/dev/null 2>&1 || true
# momentum scrolling sends its glide through a virtual scroll device (see 72-summit-uinput.rules)
modprobe uinput >/dev/null 2>&1 || true
udevadm trigger --action=change --sysname-match=uinput >/dev/null 2>&1 || true
# make sure the drive starts on a Mac through the generic "EFI Boot" path (fixes 1.0–1.21 installs)
[ "${SUMMIT_LIVE:-0}" = 1 ] || /usr/local/sbin/summit-efi-sync || true
exit 0
