#!/bin/bash
# Runs once per user, inside their desktop session, after an update is installed.
systemctl --user daemon-reload >/dev/null 2>&1
systemctl --user enable summit-update-watch.path >/dev/null 2>&1
systemctl --user restart summit-update-watch.path >/dev/null 2>&1
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
# 1.25.1: the desktop portal reads its new settings (light/dark for App Store apps) when it starts
if [ -f /usr/share/xdg-desktop-portal/xfce-portals.conf ] && [ ! -e "$HOME/.config/summit/portal-1251" ]; then
  touch "$HOME/.config/summit/portal-1251"
  systemctl --user try-restart xdg-desktop-portal.service >/dev/null 2>&1
fi
# 1.29.0: the same window buttons in every app (App Store apps and browsers; see summit-window-buttons)
summit-window-buttons >/dev/null 2>&1
# 1.29.0: photo wallpapers. The drawn Forest and Meadow pictures are gone and the default is now the Summit
# photograph; anyone still on the old default or a removed picture moves to it once (other choices are kept)
if [ ! -e "$HOME/.config/summit/walls-1290" ]; then
  mkdir -p "$HOME/.config/summit"; touch "$HOME/.config/summit/walls-1290"
  w=$(summit-appearance get 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("wallpaper",""))' 2>/dev/null)
  case "$w" in spectrum|forest|hills|"") summit-appearance set wallpaper=summit >/dev/null 2>&1 ;;
               peaks|lake|coast|dunes) summit-appearance apply >/dev/null 2>&1 ;; esac
fi
exit 0
