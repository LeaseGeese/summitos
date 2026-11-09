#!/bin/bash
# Adds over-the-air updates to a computer already running Summit OS 1.2x, then installs the latest update.
#   curl -fsSL https://raw.githubusercontent.com/OWNER/summitos/main/tools/install-updater.sh | sudo bash
set -euo pipefail
REPO="${SUMMIT_REPO:-LeaseGeese/summitos}"
API="${SUMMIT_API:-https://api.github.com}"; RAW="${SUMMIT_RAW:-https://raw.githubusercontent.com}"; CL="${SUMMIT_CODELOAD:-https://codeload.github.com}"
[ "$(id -u)" = 0 ] || { echo "Please run with sudo."; exit 1; }
grep -q "Summit OS" /etc/os-release || { echo "This doesn't look like Summit OS."; exit 1; }
echo "Setting up Summit OS updates from github.com/$REPO …"
mkdir -p /etc/summit /usr/local/sbin
curl -fsSL "$RAW/$REPO/main/overlay/usr/local/sbin/summit-update" -o /usr/local/sbin/summit-update
chmod 755 /usr/local/sbin/summit-update
[ -f /etc/summit/update.json ] || echo '{}' > /etc/summit/update.json
summit-update set repo="$REPO" api="$API" raw="$RAW" codeload="$CL" >/dev/null
summit-update install --force
# bring the current desktop session up to date too
U="${SUDO_USER:-}"
if [ -n "$U" ] && [ "$U" != root ]; then
  UID_=$(id -u "$U")
  sudo -u "$U" XDG_RUNTIME_DIR=/run/user/$UID_ DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UID_/bus DISPLAY=:0 \
    bash -c 'systemctl --user daemon-reload; systemctl --user enable --now summit-update-watch.path; summit-update-session' || true
fi
echo
echo "Done. Open Settings → Software Update to turn on automatic updates or Live testing."
