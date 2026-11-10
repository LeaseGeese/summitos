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
# 1.22.3: load Summit's GTK module (hides the underlined letters in the menu bar)
cur=$(xfconf-query -c xsettings -p /Gtk/Modules 2>/dev/null)
case ":$cur:" in
  *:summit-gtk-module:*) ;;
  *) xfconf-query -c xsettings -p /Gtk/Modules -n -t string -s "${cur:+$cur:}summit-gtk-module" ;;
esac
# 1.23.0: App Store in the dock, right after Launchpad (once; if you remove it, it stays removed)
L="$HOME/.config/plank/dock1/launchers"
if [ -d "$L" ] && [ ! -e "$HOME/.config/summit/appstore-docked" ]; then
  mkdir -p "$HOME/.config/summit"; touch "$HOME/.config/summit/appstore-docked"
  printf '[PlankDockItemPreferences]\nLauncher=file:///usr/share/applications/summit-appstore.desktop\n' > "$L/appstore.dockitem"
  items=$(dconf read /net/launchpad/plank/docks/dock1/dock-items)
  case "$items" in
    *appstore.dockitem*) ;;
    *launchpad.dockitem*) dconf write /net/launchpad/plank/docks/dock1/dock-items "$(echo "$items" | sed "s/'launchpad.dockitem'/'launchpad.dockitem', 'appstore.dockitem'/")" ;;
    "") ;;
    *) dconf write /net/launchpad/plank/docks/dock1/dock-items "$(echo "$items" | sed "s/\]$/, 'appstore.dockitem']/")" ;;
  esac
fi
# 1.23.3: Control+Command+F toggles full screen, like macOS
# (only into a personal shortcut list that already exists: a list with just this one would hide the others)
if xfconf-query -c xfce4-keyboard-shortcuts -l 2>/dev/null | grep -q "^/xfwm4/custom/<Super>q$"; then
  xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Primary><Super>f" -n -t string -s fullscreen_key 2>/dev/null
fi
exit 0
