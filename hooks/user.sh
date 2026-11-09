#!/bin/bash
# Runs once per user, inside their desktop session, after an update is installed.
systemctl --user daemon-reload >/dev/null 2>&1
systemctl --user enable summit-update-watch.path >/dev/null 2>&1
systemctl --user restart summit-update-watch.path >/dev/null 2>&1
# one-time fix for 1.22.2–1.22.5: restart the dock/Spotlight that were holding the refresh lock
if fuser "${XDG_RUNTIME_DIR:-/tmp}/summit-update-session.lock" >/dev/null 2>&1; then
  pkill -u "$(id -u)" -x plank; pkill -u "$(id -u)" -f bin/summit-shell; sleep 1
  systemd-run --user --quiet --collect --scope -- setsid plank >/dev/null 2>&1 </dev/null 9>&- &
  systemd-run --user --quiet --collect --scope -- setsid summit-shell >/dev/null 2>&1 </dev/null 9>&- &
fi
exit 0
