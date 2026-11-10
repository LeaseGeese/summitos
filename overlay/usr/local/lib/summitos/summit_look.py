"""summit_look: quick access to Summit OS's appearance settings for apps (Settings, Control Center).

Reading is a plain file read, and changes are handed to summit-shell (always running), which applies
them in-process behind a crossfade, so nothing has to start up. If summit-shell isn't running,
the `summit-appearance` command does the work instead.
"""
import datetime, json, os, subprocess

STATE = os.path.join(os.path.expanduser("~"), ".config", "summit", "appearance.json")
DEFAULTS = {"accent": "blue", "mode": "light", "wallpaper": "spectrum", "glass": "on",
            "dock_size": 52, "dock_zoom": True, "dock_autohide": False, "text": "default"}

def get():
    s = dict(DEFAULTS)
    try:
        with open(STATE) as f: s.update(json.load(f))
    except (OSError, ValueError):
        pass
    if s.get("mode") == "auto":
        now = datetime.datetime.now(); m = now.hour * 60 + now.minute
        s["effective_dark"] = not (6 * 60 + 30 <= m < 19 * 60 + 30)
    else:
        s["effective_dark"] = s.get("mode") == "dark"
    return s

LOCAL = None      # summit-shell sets this to its own handler (Control Center runs inside summit-shell)

def set(**kv):
    """Change settings, e.g. set(mode="dark"). Returns at once; the change happens in the background."""
    pairs = [f"{k}={'true' if v is True else 'false' if v is False else v}" for k, v in kv.items()]
    if LOCAL is not None:
        LOCAL(pairs); return
    try:
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.summitos.Shell", "/org/summitos/Shell", "org.gtk.Actions", "Activate",
                      GLib.Variant("(sava{sv})", ("appearance", [GLib.Variant("s", " ".join(pairs))], {})),
                      None, Gio.DBusCallFlags.NO_AUTO_START, 1500, None)
        return
    except Exception:
        pass
    try:
        subprocess.Popen(["summit-appearance", "set"] + pairs, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
