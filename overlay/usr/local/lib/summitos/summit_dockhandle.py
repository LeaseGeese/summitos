"""Resize the Dock by dragging, like on a Mac.

The two ends of the Dock (the empty glass beside the first and the last icon) are handles: the pointer turns
into an up/down arrow there, dragging up makes the Dock bigger and dragging down makes it smaller. A right
click on a handle opens a small menu (magnification, hiding, Dock settings).

Runs inside summit-shell. It only wakes up when the Dock changes shape or a window opens or closes, and it
steps aside whenever something goes wrong: the Dock itself is never touched except for its icon size.

It also keeps the Dock from outgrowing the screen. The Dock (plank) can lock up when its icons no longer fit,
so the icons are made a little smaller while many apps are open and go back to the size you chose afterwards."""
import os, json, subprocess, time
import gi
gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Gio

MIN_SIZE, MAX_SIZE = 32, 80
PLANK_PATH = "/net/launchpad/plank/docks/dock1/"
STATE = os.path.join(os.path.expanduser("~"), ".config", "summit", "appearance.json")
SPARE = 2          # room kept for this many more icons, so newly opened apps can never push the Dock off the screen


def theme_padding(name):
    """(space between icons, space at each end) of a Dock theme, as fractions of the icon size."""
    item, horiz = 1.0, 0.8
    for base in (os.path.join(GLib.get_user_data_dir(), "plank", "themes"), "/usr/share/plank/themes"):
        try:
            for line in open(os.path.join(base, name, "dock.theme")):
                k, _, v = line.partition("=")
                if k.strip() == "ItemPadding": item = float(v) / 10
                elif k.strip() == "HorizPadding": horiz = float(v) / 10
            break
        except (OSError, ValueError):
            continue
    return max(0.0, item), max(0.0, horiz)


class Handle(Gtk.Window):
    """One invisible grab area at an end of the Dock."""
    def __init__(self, owner):
        super().__init__(type=Gtk.WindowType.TOPLEVEL, title="Dock Handle")
        self.owner = owner; self.hot = False
        self.set_wmclass("summit-dock-handle", "Summit-dock-handle")
        vis = self.get_screen().get_rgba_visual()
        if vis: self.set_visual(vis)
        self.set_app_paintable(True); self.set_decorated(False); self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)       # same layer as the Dock: full-screen windows cover both
        self.set_skip_taskbar_hint(True); self.set_skip_pager_hint(True)
        self.set_accept_focus(False); self.set_focus_on_map(False)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.on_draw)
        self.connect("realize", lambda w: w.get_window().set_cursor(Gdk.Cursor.new_from_name(w.get_display(), "ns-resize")))
        self.connect("enter-notify-event", lambda *_: self.light(True))
        self.connect("leave-notify-event", lambda *_: self.owner.drag is None and self.light(False))
        self.connect("button-press-event", owner.on_press)
        self.connect("motion-notify-event", owner.on_motion)
        self.connect("button-release-event", owner.on_release)

    def light(self, on):
        if on != self.hot: self.hot = on; self.queue_draw()
        return False

    def on_draw(self, w, cr):
        cr.set_operator(0); cr.paint(); cr.set_operator(2)          # clear: the handle is see-through
        if self.hot:                                                # a short grip line while the pointer is on it
            a = w.get_allocation(); h = a.height * 0.42; x = a.width / 2; y = (a.height - h) / 2
            dark = self.owner.dark()
            cr.set_line_width(3); cr.set_line_cap(1)
            cr.set_source_rgba(1, 1, 1, 0.75) if dark else cr.set_source_rgba(0.1, 0.1, 0.15, 0.55)
            cr.move_to(x, y); cr.line_to(x, y + h); cr.stroke()
        return True


class DockHandle:
    def __init__(self, shell):
        from Xlib import display, X                   # python3-xlib; without it there are simply no handles
        from Xlib.ext import shape
        self.X = X; self.shape = shape; self.shell = shell
        self.d = display.Display()
        if not self.d.has_extension("SHAPE"): raise RuntimeError("no SHAPE extension")
        self.root = self.d.screen().root
        self.client_list = self.d.intern_atom("_NET_CLIENT_LIST")
        self.root.change_attributes(event_mask=X.PropertyChangeMask)
        self.settings = Gio.Settings.new_with_path("net.launchpad.plank.dock.settings", PLANK_PATH)
        self.dock = None; self.rect = None; self.drag = None; self._pending = None; self.items = 0
        self.changed_at = 0.0; self.retries = 0; self.cpu = None; self.busy = 0
        self.settings.connect("changed::icon-size", self.on_size_changed)
        GLib.timeout_add_seconds(20, self.watch)
        self.handles = [Handle(self), Handle(self)]
        GLib.io_add_watch(self.d.fileno(), GLib.IO_IN, self.on_x)
        self.find_dock(); self.later()

    def preferred(self):
        """The Dock size the person chose."""
        try: return max(MIN_SIZE, min(MAX_SIZE, int(json.load(open(STATE)).get("dock_size", 52))))
        except Exception: return 52

    def fit(self, size=None, items=None):
        """The largest icon size (up to `size`) at which the Dock, plus a little spare room, fits the screen."""
        size = self.preferred() if size is None else int(size)
        n = self.items if items is None else items
        if n <= 0: return max(MIN_SIZE, min(MAX_SIZE, size))
        try:
            item, horiz = theme_padding(self.settings.get_string("theme"))
            disp = Gdk.Display.get_default(); mon = disp.get_primary_monitor() or disp.get_monitor(0)
            width = mon.get_geometry().width * mon.get_scale_factor()
            most = int((width - 8) / ((1 + item) * (n + SPARE) + 2 * horiz + 0.1)) // 2 * 2
        except Exception:
            most = MAX_SIZE
        return max(MIN_SIZE, min(MAX_SIZE, size, most))

    def on_size_changed(self, *_):
        self.changed_at = time.monotonic(); self.later()

    # ---- a Dock that has locked up (busy without pause, drawing nothing new) is started again at a safe size
    def watch(self):
        try:
            pid = subprocess.run(["pgrep", "-n", "-x", "-u", str(os.getuid()), "plank"], capture_output=True, text=True).stdout.strip()
            if not pid: self.cpu = None; self.busy = 0; return True
            f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
            used = (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
            last, self.cpu = self.cpu, (pid, used)
            if last and last[0] == pid and used - last[1] > 15: self.busy += 1       # flat out for a whole 20 seconds
            else: self.busy = 0
            if self.busy >= 2:
                self.busy = 0; self.cpu = None
                print("dock handle: the Dock locked up, starting it again at a size that fits", flush=True)
                try: pinned = len(self.settings.get_strv("dock-items"))
                except Exception: pinned = 12
                safe = self.fit(min(self.preferred(), self.settings.get_int("icon-size")), max(self.items, pinned) + 4)
                self.settings.set_int("icon-size", safe); Gio.Settings.sync()
                subprocess.Popen(["summit-keep", "--restart", "dock"], start_new_session=True)
        except Exception:
            pass
        return True

    def dark(self):
        try: return "Dark" in self.settings.get_string("theme")
        except Exception: return False

    # ---- following the Dock
    def on_x(self, *_):
        try:
            look = False
            while self.d.pending_events():
                e = self.d.next_event()
                if e.type == self.X.PropertyNotify:
                    if e.atom == self.client_list and self.dock is None: look = True
                elif e.type == self.X.DestroyNotify:
                    if self.dock is not None and e.window.id == self.dock.id: self.dock = None; self.later()
                else:
                    self.later()                      # the Dock changed shape, moved or was hidden
            if look and self.find_dock(): self.later()
        except Exception:
            self.dock = None; self.later()
        return True

    def find_dock(self):
        self.dock = None
        try:
            prop = self.root.get_full_property(self.client_list, self.X.AnyPropertyType)
            for xid in (prop.value if prop else []):
                w = self.d.create_resource_object("window", int(xid))
                try: cls = w.get_wm_class()
                except Exception: cls = None
                if cls and cls[1] == "Plank":
                    w.change_attributes(event_mask=self.X.StructureNotifyMask)
                    w.shape_select_input(1)
                    self.d.sync(); self.dock = w; return True
        except Exception:
            self.dock = None
        return False

    def later(self):
        if self._pending is None: self._pending = GLib.timeout_add(250, self.place)

    def place(self):
        """Put the two handles on the ends of the Dock (or away, when the Dock is hidden or gone)."""
        self._pending = None
        if self.drag is not None: return False
        rect = None
        try:
            if self.dock is not None:
                rs = self.dock.shape_get_rectangles(self.shape.SK.Input).rectangles
                pos = self.root.translate_coords(self.dock, 0, 0)
                if rs:
                    x0 = min(r.x for r in rs); y0 = min(r.y for r in rs)
                    x1 = max(r.x + r.width for r in rs); y1 = max(r.y + r.height for r in rs)
                    rect = (pos.x + x0, pos.y + y0, x1 - x0, y1 - y0)
        except Exception:
            self.dock = None; rect = None
        size = self.settings.get_int("icon-size")
        horizontal = self.settings.get_string("position") in ("bottom", "top")
        if rect is None or not horizontal or rect[3] < size or rect[2] < size * 3:      # hidden, sideways or gone
            for h in self.handles: h.hide()
            self.rect = None; return False
        # how many icons the Dock holds now, and the size that keeps it on the screen
        item, horiz = theme_padding(self.settings.get_string("theme"))
        count = (rect[2] - 2 * horiz * size) / ((1 + item) * size)
        settling = time.monotonic() - self.changed_at < 0.8
        if settling or abs(count - round(count)) > 0.25:        # the Dock is still redrawing at a new size: look again
            self.retries += 1
            if settling or self.retries <= 8: self._pending = GLib.timeout_add(400, self.place); return False
        self.retries = 0
        self.items = max(1, int(round(count)))
        want = self.fit()
        if want != size:
            self.settings.set_int("icon-size", want); self.later(); return False      # placed once the Dock has redrawn
        if rect == self.rect and all(h.get_visible() for h in self.handles): return False
        self.rect = rect
        x, y, w, hgt = rect
        hw = max(12, min(24, int(size * 0.34)))            # the empty glass at each end
        top = y + int(hgt * 0.24); hh = y + hgt - top      # below the part where only icon tops stick out
        scale = self.handles[0].get_scale_factor() or 1
        for h, hx in zip(self.handles, (x, x + w - hw)):
            h.set_size_request(max(1, hw // scale), max(1, hh // scale)); h.resize(max(1, hw // scale), max(1, hh // scale))
            h.move(hx // scale, top // scale)
            if not h.get_visible(): h.show()
            h.move(hx // scale, top // scale)
            try:                                       # belongs to the Dock: the window manager keeps it just above it
                self.d.create_resource_object("window", h.get_window().get_xid()).set_wm_transient_for(self.dock)
            except Exception: pass
        try: self.d.flush()
        except Exception: pass
        return False

    # ---- dragging
    def on_press(self, w, e):
        if e.button == 3: self.menu(e); return True
        if e.button != 1: return False
        self.drag = (e.y_root, self.settings.get_int("icon-size")); w.light(True)
        return True

    def on_motion(self, w, e):
        if self.drag is None: return False
        y0, s0 = self.drag
        size = int(round((s0 + (y0 - e.y_root) * 0.8) / 2.0)) * 2
        size = self.fit(size)
        if size != self.settings.get_int("icon-size"): self.settings.set_int("icon-size", size)
        return True

    def on_release(self, w, e):
        if e.button != 1 or self.drag is None: return False
        self.drag = None
        for h in self.handles: h.light(False)
        size = self.settings.get_int("icon-size")
        try: self.shell.change_appearance([f"dock_size={size}"])       # remembered, and the Settings slider follows
        except Exception: pass
        self.later()
        return True

    # ---- the menu
    def menu(self, e):
        m = Gtk.Menu()
        def item(label, fn):
            i = Gtk.MenuItem(label=label); i.connect("activate", lambda *_: fn()); m.append(i)
        zoom = self.settings.get_boolean("zoom-enabled"); hiding = self.settings.get_string("hide-mode") != "none"
        look = lambda *kv: self.shell.change_appearance(list(kv))
        item("Turn Magnification Off" if zoom else "Turn Magnification On", lambda: look(f"dock_zoom={'false' if zoom else 'true'}"))
        item("Turn Hiding Off" if hiding else "Turn Hiding On", lambda: look(f"dock_autohide={'false' if hiding else 'true'}"))
        m.append(Gtk.SeparatorMenuItem())
        for name, size in (("Small", 40), ("Medium", 52), ("Large", 68)):
            item(name, lambda s=size: look(f"dock_size={s}"))
        m.append(Gtk.SeparatorMenuItem())
        item("Dock Settings…", lambda: subprocess.Popen(["summit-settings", "--page", "appearance"], start_new_session=True))
        m.show_all(); m.popup_at_pointer(e)
        self._menu = m


def start(shell):
    """Called by summit-shell once the desktop is up. Returns the handle keeper, or None."""
    if os.path.exists(os.path.join(os.path.expanduser("~"), ".config", "summit", "no-dock-resize")): return None
    try: return DockHandle(shell)
    except Exception as e:
        print("dock handle:", e); return None
