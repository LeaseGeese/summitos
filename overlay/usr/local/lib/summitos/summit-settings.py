#!/usr/bin/python3
"""Summit Settings: Appearance, Storage, Sharing and About in one window.
   summit-settings [--page appearance|storage|mouse|sharing|bluetooth|update|about] [--welcome]"""
import os, sys, json, socket, subprocess, threading, shutil, re, time
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango, Gio

HOME = os.path.expanduser("~")
USER = os.environ.get("USER") or os.getlogin()
HOST = socket.gethostname()
WALLS = "/usr/share/backgrounds/summitos"
CFG = os.path.join(HOME, ".config", "summit")
AUTOSTART = os.path.join(HOME, ".config", "autostart")
LIVE = "boot=casper" in open("/proc/cmdline").read()
STORAGE_MNT = "/mnt/imac-hd"
ACCENT_HEX = {"blue": "#1A73E8", "purple": "#9C3FD1", "pink": "#E0306F", "orange": "#EF6C00",
              "yellow": "#F5C400", "green": "#2E9E4F", "silver": "#9AA3AE"}
ACCENT_ORDER = ["blue", "purple", "pink", "orange", "yellow", "green", "silver"]
NATURE_ORDER = ["peaks", "lake", "coast", "dunes", "forest", "hills"]
NATURE_NAMES = {"peaks": "Peaks", "lake": "Alpine Lake", "coast": "Coast", "dunes": "Dunes", "forest": "Forest", "hills": "Meadow"}
WALL_ORDER = ["accent", "spectrum"] + NATURE_ORDER + ACCENT_ORDER

def sh(*a, **kw):
    kw.setdefault("timeout", 30)
    try: return subprocess.run(list(a), capture_output=True, text=True, **kw)
    except Exception as e:
        class R: returncode = 1; stdout = ""; stderr = str(e)
        return R()

import summit_look                      # /usr/local/lib/summitos/summit_look.py, next to this file
def appearance():
    return summit_look.get()

_live_css = None
def reload_css():
    """Re-read the generated glass/accent CSS so this window follows changes immediately."""
    global _live_css
    scr = Gdk.Screen.get_default()
    if _live_css: Gtk.StyleContext.remove_provider_for_screen(scr, _live_css)
    _live_css = Gtk.CssProvider()
    try: _live_css.load_from_path(os.path.join(HOME, ".config", "gtk-3.0", "summit.css"))
    except GLib.Error: return False
    Gtk.StyleContext.add_provider_for_screen(scr, _live_css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
    return False

def set_appearance(**kv):
    # summit-shell applies it (instantly, behind a crossfade); this window follows the new colours
    # when the generated stylesheet changes (see watch_css)
    summit_look.set(**kv)

_css_mon = None
def watch_css():
    global _css_mon
    f = Gio.File.new_for_path(os.path.join(HOME, ".config", "gtk-3.0", "summit.css"))
    _css_mon = f.monitor_file(Gio.FileMonitorFlags.NONE, None)
    _css_mon.connect("changed", lambda *_: GLib.timeout_add(150, reload_css))

def human(n):
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB": return f"{n:.0f} {unit}" if unit in ("bytes", "KB") else f"{n:.1f} {unit}".replace(".0 ", " ")
        n /= 1000

def label(text, cls=None, xalign=0, wrap=True, markup=False):
    l = Gtk.Label(xalign=xalign, wrap=wrap)
    l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    (l.set_markup if markup else l.set_text)(text)
    if cls:
        for c in cls.split(): l.get_style_context().add_class(c)
    return l

def card(*children, spacing=10):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    b.get_style_context().add_class("summit-card")
    b.set_margin_bottom(14)
    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing, margin=16)
    for c in children: inner.pack_start(c, False, False, 0)
    b.pack_start(inner, True, True, 0)
    return b

def section(title, subtitle=None):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    b.pack_start(label(f"<b>{GLib.markup_escape_text(title)}</b>", markup=True), False, False, 0)
    if subtitle: b.pack_start(label(subtitle, "summit-subtle"), False, False, 0)
    return b

def rounded_thumb(path, w, h, radius=12):
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, w, h, False)
    except GLib.Error:
        return Gtk.Image.new_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
    da = Gtk.DrawingArea(); da.set_size_request(w, h)
    def draw(_w, cr):
        import math
        r = radius
        cr.new_sub_path()
        cr.arc(w - r, r, r, -math.pi / 2, 0); cr.arc(w - r, h - r, r, 0, math.pi / 2)
        cr.arc(r, h - r, r, math.pi / 2, math.pi); cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.close_path(); cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0); cr.paint()
    da.connect("draw", draw)
    return da

def add_css(widget, css):
    p = Gtk.CssProvider(); p.load_from_data(css.encode())
    widget.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

# ======================================================================= Appearance
class AppearancePage(Gtk.Box):
    def __init__(self, compact=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.state = appearance()
        self._lock = False
        self.compact = compact
        # mode
        modes = Gtk.Box(spacing=14, homogeneous=True)
        self.mode_btns = {}
        for key, name in (("light", "Light"), ("dark", "Dark"), ("auto", "Auto")):
            btn = Gtk.ToggleButton(relief=Gtk.ReliefStyle.NONE); btn.get_style_context().add_class("summit-pick")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            if key == "auto":
                pic = Gtk.Box(); pic.pack_start(rounded_thumb(f"{WALLS}/thumbs/summit-spectrum-light.png", 70, 88, 10), False, False, 0)
                pic.pack_start(rounded_thumb(f"{WALLS}/thumbs/summit-spectrum-dark.png", 70, 88, 10), False, False, 0)
            else:
                pic = rounded_thumb(f"{WALLS}/thumbs/summit-spectrum-{key}.png", 140, 88, 10)
            v.pack_start(pic, False, False, 0)
            v.pack_start(label(name, xalign=0.5), False, False, 0)
            btn.add(v); btn.connect("toggled", self.on_mode, key)
            self.mode_btns[key] = btn; modes.pack_start(btn, True, True, 0)
        auto_note = label("Auto switches to Dark from 7:30 PM to 6:30 AM.", "summit-subtle")
        # accent
        acc = Gtk.Box(spacing=12)
        self.acc_btns = {}
        for a in ACCENT_ORDER:
            b = Gtk.Button(); b.set_size_request(34, 34); b.set_tooltip_text(a.capitalize())
            b.get_style_context().add_class("summit-swatch")
            add_css(b, f"button {{ background-image: none; background-color: {ACCENT_HEX[a]}; }}")
            b.connect("clicked", self.on_accent, a); self.acc_btns[a] = b
            acc.pack_start(b, False, False, 0)
        self.acc_name = label("", "summit-subtle"); acc.pack_start(self.acc_name, False, False, 8)
        # wallpaper
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=5, min_children_per_line=3,
                           column_spacing=10, row_spacing=10, homogeneous=True)
        self.wall_btns = {}
        for w in WALL_ORDER:
            name = {"accent": "Matches accent", "spectrum": "Spectrum", **NATURE_NAMES}.get(w, w.capitalize())
            thumbname = "blue" if w == "accent" else w
            b = Gtk.ToggleButton(relief=Gtk.ReliefStyle.NONE); b.get_style_context().add_class("summit-pick")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self.wall_thumb_box = None
            v.pack_start(rounded_thumb(f"{WALLS}/thumbs/summit-{thumbname}-light.png", 120, 68, 9), False, False, 0)
            v.pack_start(label(name, "summit-subtle", xalign=0.5), False, False, 0)
            b.add(v); b.connect("toggled", self.on_wall, w); self.wall_btns[w] = b
            flow.add(b)
        pick = Gtk.Button(label="Choose a Picture…"); pick.connect("clicked", self.on_pick)
        # glass
        glass = Gtk.Box(spacing=0); glass.get_style_context().add_class("linked")
        self.glass_btns = {}
        for key, name in (("on", "Liquid Glass"), ("reduced", "Reduced"), ("off", "Solid")):
            b = Gtk.ToggleButton(label=name); b.connect("toggled", self.on_glass, key)
            self.glass_btns[key] = b; glass.pack_start(b, True, True, 0)
        glass_note = label("Liquid Glass blurs what's behind the menu bar, menus, Spotlight and Launchpad. "
                           "Reduced and Solid use less graphics power and are easier to read.", "summit-subtle")
        # text size
        txt = Gtk.Box(spacing=0); txt.get_style_context().add_class("linked")
        self.text_btns = {}
        for key, name in (("small", "Small"), ("default", "Default"), ("large", "Large"), ("larger", "Larger")):
            b = Gtk.ToggleButton(label=name); b.connect("toggled", self.on_text, key)
            self.text_btns[key] = b; txt.pack_start(b, True, True, 0)
        # dock
        self.size = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 32, 80, 2)
        self.size.set_draw_value(False); self.size.get_style_context().add_class("summit")
        self.size.add_mark(32, Gtk.PositionType.BOTTOM, "Small"); self.size.add_mark(80, Gtk.PositionType.BOTTOM, "Large")
        self._size_timer = None
        self.size.connect("value-changed", self.on_size)
        self.zoom = Gtk.Switch(valign=Gtk.Align.CENTER); self.zoom.connect("notify::active", self.on_switch, "dock_zoom")
        self.hide = Gtk.Switch(valign=Gtk.Align.CENTER); self.hide.connect("notify::active", self.on_switch, "dock_autohide")

        def row(text, widget):
            b = Gtk.Box(spacing=12); b.pack_start(label(text), True, True, 0); b.pack_end(widget, False, False, 0); return b

        self.pack_start(card(section("Appearance"), modes, auto_note), False, False, 0)
        self.pack_start(card(section("Accent colour", "Inspired by the iMac colours. Sets highlights, folders and buttons."), acc), False, False, 0)
        if not compact:
            self.pack_start(card(section("Wallpaper"), flow, pick), False, False, 0)
            self.pack_start(card(section("Glass effects"), glass, glass_note), False, False, 0)
            self.pack_start(card(section("Text size"), txt), False, False, 0)
            dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            dock.pack_start(row("Size", self.size), False, False, 0)
            self.size.set_size_request(260, -1)
            dock.pack_start(row("Magnify icons on hover", self.zoom), False, False, 0)
            dock.pack_start(row("Hide the dock when a window covers it", self.hide), False, False, 0)
            tip = label("You can also drag either end of the Dock up or down to resize it, or right-click there for "
                        "quick options. With many apps open the icons shrink a little so the Dock always fits the screen.", "summit-subtle")
            tip.set_line_wrap(True); tip.set_xalign(0); dock.pack_start(tip, False, False, 0)
            self.pack_start(card(section("Dock"), dock), False, False, 0)
        self.refresh()

    def refresh(self):
        s = self.state; self._lock = True
        for k, b in self.mode_btns.items(): b.set_active(s.get("mode") == k)
        for k, b in self.acc_btns.items():
            ctx = b.get_style_context()
            (ctx.add_class if s.get("accent") == k else ctx.remove_class)("selected")
        self.acc_name.set_text((s.get("accent") or "blue").capitalize())
        for k, b in self.wall_btns.items(): b.set_active(s.get("wallpaper") == k)
        for k, b in self.glass_btns.items(): b.set_active(s.get("glass") == k)
        for k, b in self.text_btns.items(): b.set_active(s.get("text", "default") == k)
        self.size.set_value(int(s.get("dock_size", 52)))
        self.zoom.set_active(bool(s.get("dock_zoom", True))); self.hide.set_active(bool(s.get("dock_autohide", False)))
        self._lock = False

    def change(self, **kv):
        if self._lock: return
        self.state.update(kv); self.refresh(); set_appearance(**kv)

    def on_mode(self, b, key):
        if self._lock: return
        if not b.get_active(): self.refresh(); return
        self.change(mode=key)
    def on_accent(self, _b, a): self.change(accent=a)
    def on_wall(self, b, w):
        if self._lock: return
        if not b.get_active(): self.refresh(); return
        self.change(wallpaper=w)
    def on_glass(self, b, key):
        if self._lock: return
        if not b.get_active(): self.refresh(); return
        self.change(glass=key)
    def on_text(self, b, key):
        if self._lock: return
        if not b.get_active(): self.refresh(); return
        self.change(text=key)
    def on_switch(self, sw, _p, key):
        if self._lock: return
        self.change(**{key: "true" if sw.get_active() else "false"}); self.state[key] = sw.get_active()
    def on_size(self, sc):
        if self._lock: return
        if self._size_timer: GLib.source_remove(self._size_timer)
        def fire():
            self._size_timer = None; v = int(sc.get_value()); self.state["dock_size"] = v
            set_appearance(dock_size=v); return False
        self._size_timer = GLib.timeout_add(350, fire)
    def on_pick(self, _b):
        d = Gtk.FileChooserDialog(title="Choose a Picture", transient_for=self.get_toplevel(), action=Gtk.FileChooserAction.OPEN)
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Choose", Gtk.ResponseType.ACCEPT)
        f = Gtk.FileFilter(); f.set_name("Pictures"); f.add_mime_type("image/*"); d.add_filter(f)
        d.set_current_folder(os.path.join(HOME, "Pictures") if os.path.isdir(os.path.join(HOME, "Pictures")) else HOME)
        if d.run() == Gtk.ResponseType.ACCEPT:
            self.change(wallpaper=d.get_filename())
        d.destroy()

# ======================================================================= Storage
def disks():
    r = sh("lsblk", "-J", "-b", "-o", "NAME,PATH,MODEL,SIZE,ROTA,TYPE,TRAN,RM,MOUNTPOINTS,FSTYPE,LABEL")
    try: data = json.loads(r.stdout)["blockdevices"]
    except Exception: return []
    out = []
    for d in data:
        if d.get("type") != "disk" or (d.get("name") or "").startswith(("loop", "sr", "zram", "ram")): continue
        if int(d.get("size") or 0) < 8_000_000_000: continue
        mps, labels = [], []
        for c in [d] + (d.get("children") or []):
            mps += [m for m in (c.get("mountpoints") or []) if m]
            if c.get("label"): labels.append(c["label"])
        d["all_mounts"] = mps; d["labels"] = labels
        out.append(d)
    return out

def usage(path):
    try:
        st = os.statvfs(path); total = st.f_blocks * st.f_frsize; free = st.f_bavail * st.f_frsize
        return total, total - free
    except OSError: return None

class StoragePage(Gtk.Box):
    def __init__(self, header=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        if header:
            self.pack_start(card(section("Storage", "Your drives, how full they are and how healthy they look.")), False, False, 0)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.pack_start(self.list, False, False, 0)
        self.health = {}
        self.reload()
        threading.Thread(target=self.load_health, daemon=True).start()

    def load_health(self):
        try: data = json.loads(sh("summit-disk-health", "--json", timeout=20).stdout or "[]")
        except ValueError: data = []
        self.health = {d["model"]: d for d in data}
        GLib.idle_add(self.reload)

    def reload(self):
        for c in self.list.get_children(): self.list.remove(c)
        for d in disks():
            self.list.pack_start(self.disk_card(d), False, False, 0)
        self.list.show_all(); return False

    def disk_card(self, d):
        system = "/" in d["all_mounts"]
        storage = STORAGE_MNT in d["all_mounts"] or "iMac HD" in d["labels"]
        ssd = str(d.get("rota")) in ("0", "False", "false")
        usb = d.get("tran") == "usb"
        model = (d.get("model") or "Drive").strip().replace("_", " ")
        kind = ("SSD" if ssd else "Hard drive") + (" · USB" if usb else " · internal")
        head = Gtk.Box(spacing=14)
        icon = Gtk.Image.new_from_icon_name("drive-harddisk-solidstate" if ssd else "drive-harddisk", Gtk.IconSize.DIALOG)
        icon.set_pixel_size(48); head.pack_start(icon, False, False, 0)
        t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        badge = " — <b>Startup disk</b>" if system else (" — <b>iMac HD storage</b>" if storage else "")
        t.pack_start(label(f"<b>{GLib.markup_escape_text(model)}</b>{badge}", markup=True), False, False, 0)
        t.pack_start(label(f"{human(int(d.get('size') or 0))} {kind}", "summit-subtle"), False, False, 0)
        h = self.health.get((d.get("model") or "").strip())
        if h:
            mark = {"ok": "✅", "warning": "⚠️", "critical": "⛔"}.get(h["status"], "")
            t.pack_start(label(f"{mark} {h['text']}", "summit-subtle"), False, False, 0)
        head.pack_start(t, True, True, 0)
        box = [head]
        mp = "/" if system else (STORAGE_MNT if STORAGE_MNT in d["all_mounts"] else (d["all_mounts"][0] if d["all_mounts"] else None))
        if mp:
            u = usage(mp)
            if u and u[0] > 0:
                bar = Gtk.LevelBar(); bar.set_min_value(0); bar.set_max_value(1); bar.set_value(u[1] / u[0])
                bar.set_size_request(-1, 10)
                box += [bar, label(f"{human(u[1])} used of {human(u[0])} · {human(u[0]-u[1])} free", "summit-subtle")]
        actions = Gtk.Box(spacing=8)
        if storage and STORAGE_MNT in d["all_mounts"]:
            o = Gtk.Button(label="Open iMac HD"); o.connect("clicked", lambda *_: subprocess.Popen(["thunar", STORAGE_MNT])); actions.pack_start(o, False, False, 0)
        elif not system and not usb and not LIVE:
            b = Gtk.Button(label="Use This Drive for Storage…"); b.get_style_context().add_class("suggested-action")
            b.connect("clicked", self.setup, d); actions.pack_start(b, False, False, 0)
            box.append(label("Turns this drive into “iMac HD”: extra space for your Documents, Downloads, Pictures, "
                             "Music, Videos and Time Machine backups, while Summit runs fast from the SSD.", "summit-subtle"))
        elif not system and LIVE:
            box.append(label("Install Summit first, then set this drive up for storage here.", "summit-subtle"))
        if actions.get_children(): box.append(actions)
        return card(*box)

    def setup(self, _b, d):
        model = (d.get("model") or "this drive").strip().replace("_", " ")
        dlg = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True, message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.NONE, text=f"Erase “{model}” and use it for storage?")
        what = ", ".join(sorted(set(c.get("fstype") or "?" for c in (d.get("children") or [])))) or "no partitions"
        dlg.format_secondary_text(f"Everything on this {human(int(d.get('size') or 0))} drive will be erased (currently: {what}). "
                                  "This can't be undone. Back up anything you need first.")
        move = Gtk.CheckButton(label="Keep my Documents, Downloads, Pictures, Music and Videos on iMac HD", active=True)
        move.set_margin_start(12); move.set_margin_end(12)
        dlg.get_message_area().pack_start(move, False, False, 6); move.show()
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        er = dlg.add_button("Erase and Set Up", Gtk.ResponseType.OK); er.get_style_context().add_class("destructive-action")
        r = dlg.run(); move_folders = move.get_active(); dlg.destroy()
        if r != Gtk.ResponseType.OK: return
        spin = Gtk.Dialog(title="Setting up iMac HD", transient_for=self.get_toplevel(), modal=True)
        spin.set_default_size(380, 140); spin.set_resizable(False)
        bx = spin.get_content_area(); bx.set_spacing(12); bx.set_margin_top(18); bx.set_margin_bottom(18); bx.set_margin_start(24); bx.set_margin_end(24)
        sp = Gtk.Spinner(); sp.start(); bx.add(sp); bx.add(label("Erasing and preparing the drive…", xalign=0.5)); spin.show_all()
        def work():
            r = sh("pkexec", "/usr/local/libexec/summit-storage-helper", "setup", d["path"], timeout=600)
            msg = None
            if r.returncode == 0 and move_folders:
                msg = relocate_folders()
            GLib.idle_add(done, r, msg)
        def done(r, msg):
            spin.destroy()
            if r.returncode == 0:
                m = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True, message_type=Gtk.MessageType.INFO,
                                      buttons=Gtk.ButtonsType.OK, text="iMac HD is ready")
                m.format_secondary_text("It appears in Files' sidebar. " + (msg or "")); m.run(); m.destroy()
            elif r.returncode not in (126, 127):
                m = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True, message_type=Gtk.MessageType.ERROR,
                                      buttons=Gtk.ButtonsType.OK, text="Couldn't set up the drive")
                m.format_secondary_text((r.stderr or "").strip()[-400:]); m.run(); m.destroy()
            self.reload(); return False
        threading.Thread(target=work, daemon=True).start()

def relocate_folders():
    base = os.path.join(STORAGE_MNT, USER)
    if not os.path.isdir(base): return "Your folders stayed on the SSD."
    moved = []
    for name in ("Documents", "Downloads", "Pictures", "Music", "Videos"):
        src = os.path.join(HOME, name); dst = os.path.join(base, name)
        os.makedirs(dst, exist_ok=True)
        if os.path.islink(src): continue
        if os.path.isdir(src):
            for item in os.listdir(src):
                target = os.path.join(dst, item)
                if not os.path.exists(target): shutil.move(os.path.join(src, item), target)
            try: os.rmdir(src)
            except OSError: continue
        os.symlink(dst, src); moved.append(name)
    return (", ".join(moved) + " now live on iMac HD.") if moved else ""

# ======================================================================= Sharing
def active(unit): return sh("systemctl", "is-active", "--quiet", unit).returncode == 0
def autostart_path(key): return os.path.join(AUTOSTART, f"summit-{key}.desktop")
def set_autostart(key, name, cmd, on):
    p = autostart_path(key)
    if on:
        os.makedirs(AUTOSTART, exist_ok=True)
        with open(p, "w") as f:
            f.write(f"[Desktop Entry]\nType=Application\nName={name}\nExec={cmd}\nNoDisplay=true\nX-XFCE-Autostart-Override=true\n")
    elif os.path.exists(p): os.remove(p)
def tm_enabled():
    try: return "fruit:time machine = yes" in open("/etc/samba/smb.conf").read()
    except OSError: return False

class SwitchRow(Gtk.Box):
    def __init__(self, icon, title, subtitle, on, toggled, extra=None):
        super().__init__(spacing=14)
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DND); img.set_pixel_size(32)
        self.pack_start(img, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        txt.pack_start(label(f"<b>{GLib.markup_escape_text(title)}</b>", markup=True), False, False, 0)
        txt.pack_start(label(f"<small>{subtitle}</small>", "summit-subtle", markup=True), False, False, 0)
        if extra: txt.pack_start(extra, False, False, 4)
        self.pack_start(txt, True, True, 0)
        self.switch = Gtk.Switch(active=on, valign=Gtk.Align.CENTER); self._busy = False
        self.switch.connect("notify::active", self._flip, toggled)
        self.pack_end(self.switch, False, False, 0)
    def _flip(self, sw, _p, cb):
        if self._busy: return
        if cb(sw.get_active()) is False:
            self._busy = True; sw.set_active(not sw.get_active()); self._busy = False

class SharingPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.pack_start(card(section("Sharing", f"Your Mac finds this iMac as {HOST}.local on the same Wi-Fi. Everything here is off until you turn it on.")), False, False, 0)
        self.tm_spin = Gtk.SpinButton.new_with_range(50, 4000, 50); self.tm_spin.set_value(300)
        tm = Gtk.Box(spacing=8)
        self.tm_check = Gtk.CheckButton(label="Also accept Time Machine backups, up to", active=tm_enabled())
        tm.pack_start(self.tm_check, False, False, 0); tm.pack_start(self.tm_spin, False, False, 0); tm.pack_start(Gtk.Label(label="GB"), False, False, 0)
        where = "on iMac HD" if os.path.ismount(STORAGE_MNT) else "on the startup disk"
        rows = [
            SwitchRow("folder-remote", "File Sharing", f"Your Mac: Finder → Network → <b>{HOST}</b>, or Go → Connect to Server → <tt>smb://{HOST}.local</tt>. Sign in as <b>{USER}</b>. Backups are stored {where}.", active("smbd"), self.toggle_files, tm),
            SwitchRow("preferences-desktop-remote-desktop", "Screen Sharing", f"Your Mac: Finder → Network → <b>{HOST}</b> → Share Screen.", os.path.exists(autostart_path("screen-sharing")), self.toggle_screen),
            SwitchRow("video-display", "AirPlay Receiver", "Your Mac: Control Center → Screen Mirroring → pick this iMac.", os.path.exists(autostart_path("airplay")), self.toggle_airplay),
            SwitchRow("input-keyboard", "Keyboard & Mouse Sharing", "Use your MacBook's keyboard and trackpad here, with a shared clipboard. Install <b>Deskflow</b> on the Mac and make it the server; here choose <i>Client</i>.", os.path.exists(autostart_path("barrier")), self.toggle_barrier),
            SwitchRow("utilities-terminal", "Remote Login (SSH)", f"From Terminal on your Mac: <tt>ssh {USER}@{HOST}.local</tt>", active("ssh"), self.toggle_ssh),
        ]
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for i, r in enumerate(rows):
            if i: box.pack_start(Gtk.Separator(), False, False, 0)
            box.pack_start(r, False, False, 0)
        self.pack_start(card(box), False, False, 0)

    def ask_password(self, title, text, max_len=0):
        d = Gtk.Dialog(title=title, transient_for=self.get_toplevel(), modal=True)
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK); d.set_default_response(Gtk.ResponseType.OK)
        b = d.get_content_area(); b.set_spacing(8); b.set_margin_start(16); b.set_margin_end(16); b.set_margin_top(12)
        lab = Gtk.Label(label=text, wrap=True, xalign=0, max_width_chars=48); b.add(lab)
        e1 = Gtk.Entry(visibility=False, activates_default=True, placeholder_text="Password")
        e2 = Gtk.Entry(visibility=False, activates_default=True, placeholder_text="Verify password")
        if max_len: e1.set_max_length(max_len); e2.set_max_length(max_len)
        b.add(e1); b.add(e2); d.show_all()
        while True:
            if d.run() != Gtk.ResponseType.OK: d.destroy(); return None
            if not e1.get_text(): continue
            if e1.get_text() != e2.get_text(): lab.set_text("The passwords don't match. Try again."); continue
            pw = e1.get_text(); d.destroy(); return pw

    def helper(self, *args, stdin=None):
        r = sh("pkexec", "/usr/local/libexec/summit-connect-helper", *args, input=stdin, timeout=120)
        if r.returncode in (126, 127): return False
        if r.returncode != 0:
            m = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True, message_type=Gtk.MessageType.ERROR,
                                  buttons=Gtk.ButtonsType.OK, text=(r.stderr or "Something went wrong.").strip()); m.run(); m.destroy(); return False
        return True

    def toggle_files(self, on):
        if not on: return self.helper("files-off")
        pw = self.ask_password("File Sharing", f"Choose the password your Mac will use to connect as “{USER}”. Your login password is fine.")
        if pw is None: return False
        tm = int(self.tm_spin.get_value()) if self.tm_check.get_active() else 0
        return self.helper("files-on", str(tm), stdin=pw + "\n")
    def toggle_screen(self, on):
        if not on:
            set_autostart("screen-sharing", "", "", False); sh("summit-connect-agent", "stop-screen"); return True
        pw = self.ask_password("Screen Sharing", "Choose a Screen Sharing password (up to 8 characters).", max_len=8)
        if pw is None: return False
        os.makedirs(os.path.join(HOME, ".vnc"), exist_ok=True)
        if sh("x11vnc", "-storepasswd", pw, os.path.join(HOME, ".vnc", "passwd")).returncode != 0: return False
        set_autostart("screen-sharing", "Screen Sharing", "summit-connect-agent screen", True)
        subprocess.Popen(["summit-connect-agent", "screen"], start_new_session=True); return True
    def toggle_airplay(self, on):
        if not on:
            set_autostart("airplay", "", "", False); sh("summit-connect-agent", "stop-airplay"); return True
        set_autostart("airplay", "AirPlay Receiver", "summit-connect-agent airplay", True)
        subprocess.Popen(["summit-connect-agent", "airplay"], start_new_session=True); return True
    def toggle_barrier(self, on):
        if not on:
            set_autostart("barrier", "", "", False); sh("pkill", "-u", USER, "-x", "barrier"); sh("pkill", "-u", USER, "-x", "barrierc"); return True
        set_autostart("barrier", "Keyboard & Mouse Sharing", "barrier", True)
        subprocess.Popen(["barrier"], start_new_session=True); return True
    def toggle_ssh(self, on): return self.helper("ssh-on" if on else "ssh-off")

# ======================================================================= Mouse & Trackpad
class MousePage(Gtk.Box):
    """Scrolling and gestures. Each switch is a small file in ~/.config/summit that summit-gestures (scrolling,
    swipes) and summit-wm-helper (green button) read, so changes apply at once."""
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.pack_start(card(section("Mouse & Trackpad", "Scrolling and gestures for a Magic Mouse, a Magic Trackpad, or any other mouse.")), False, False, 0)
        flag = lambda name: os.path.exists(os.path.join(CFG, name))
        try: natural = open(os.path.join(CFG, "natural-scroll")).read().strip() == "on"
        except OSError: natural = False
        scroll = [
            SwitchRow("input-mouse", "Natural scrolling", "The page follows your finger: swipe up and the content moves up, as on a Mac.", natural, self.set_natural),
            SwitchRow("input-touchpad", "Momentum scrolling", "Flick on the Magic Mouse and the page glides on, slowing to a stop. Touch the mouse to stop it at once.",
                      not flag("no-momentum"), lambda on: self.set_flag("no-momentum", not on)),
        ]
        more = [
            SwitchRow("input-tablet", "Swipe gestures", "<b>Magic Mouse:</b> one finger left or right for back and forward, two fingers to switch apps, "
                      "double-tap with two fingers for Launchpad.\n<b>Trackpad:</b> two fingers for back and forward, three to switch apps, three up for Launchpad, three down for the desktop.",
                      not flag("no-gestures"), lambda on: self.set_flag("no-gestures", not on)),
            SwitchRow("view-fullscreen", "Green button fills the screen", "The green window button makes a window full screen, as on a Mac. "
                      "Off: the window fills the space below the menu bar instead.", not flag("classic-maximize"), lambda on: self.set_flag("classic-maximize", not on)),
        ]
        for title, rows in (("Scrolling", scroll), ("Gestures and windows", more)):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            box.pack_start(label(f"<b>{title}</b>", markup=True), False, False, 0)
            for i, r in enumerate(rows):
                if i: box.pack_start(Gtk.Separator(), False, False, 0)
                box.pack_start(r, False, False, 0)
            self.pack_start(card(box), False, False, 0)
        b = Gtk.Button(label="Pointer Speed and Buttons…", halign=Gtk.Align.START)
        b.connect("clicked", lambda *_: subprocess.Popen(["xfce4-mouse-settings"]))
        self.pack_start(card(section("More options", "Tracking speed, double-click speed and left-handed buttons."), b), False, False, 0)

    def set_flag(self, name, on):
        p = os.path.join(CFG, name); os.makedirs(CFG, exist_ok=True)
        try:
            if on: open(p, "w").close()
            elif os.path.exists(p): os.remove(p)
        except OSError: return False

    def set_natural(self, on):
        os.makedirs(CFG, exist_ok=True)
        try:
            with open(os.path.join(CFG, "natural-scroll"), "w") as f: f.write("on" if on else "off")
        except OSError: return False

# ======================================================================= Software Update
UPD = "/var/lib/summit-update"
def upd_json(name):
    try: return json.load(open(os.path.join(UPD, name)))
    except (OSError, ValueError): return {}
def upd_conf():
    c = {"repo": "", "branch": "main", "auto_install": False, "live": False, "interval_minutes": 360}
    try: c.update(json.load(open("/etc/summit/update.json")))
    except (OSError, ValueError): pass
    return c
def ago(t):
    if not t: return "never"
    d = int(time.time() - t)
    if d < 60: return "just now"
    if d < 3600: return f"{d // 60} min ago"
    if d < 86400: return f"{d // 3600} h ago"
    return time.strftime("%b %-d", time.localtime(t))

class UpdatePage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._lock = False
        # --- status card
        self.icon = Gtk.Image.new_from_icon_name("summitos", Gtk.IconSize.DIALOG); self.icon.set_pixel_size(72)
        self.title = label("", "summit-hero"); self.sub = label("", "summit-subtle")
        self.spin = Gtk.Spinner()
        head = Gtk.Box(spacing=16); txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        txt.pack_start(self.title, False, False, 0); txt.pack_start(self.sub, False, False, 0)
        head.pack_start(self.icon, False, False, 0); head.pack_start(txt, True, True, 0); head.pack_end(self.spin, False, False, 0)
        self.notes = label("", markup=True)
        self.btn_check = Gtk.Button(label="Check Now"); self.btn_check.connect("clicked", self.on_check)
        self.btn_install = Gtk.Button(label="Install Now"); self.btn_install.get_style_context().add_class("suggested-action")
        self.btn_install.connect("clicked", self.on_install)
        btns = Gtk.Box(spacing=8); btns.pack_start(self.btn_check, False, False, 0); btns.pack_start(self.btn_install, False, False, 0)
        self.pack_start(card(section("Software Update", "Summit checks for new versions and installs them for you."), head, self.notes, btns), False, False, 0)
        # --- settings card
        self.sw_auto = Gtk.Switch(valign=Gtk.Align.CENTER); self.sw_auto.connect("notify::active", self.on_switch, "auto_install")
        self.sw_live = Gtk.Switch(valign=Gtk.Align.CENTER); self.sw_live.connect("notify::active", self.on_switch, "live")
        def row(title, sub, w):
            b = Gtk.Box(spacing=12); t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            t.pack_start(label(f"<b>{title}</b>", markup=True), False, False, 0); t.pack_start(label(sub, "summit-subtle"), False, False, 0)
            b.pack_start(t, True, True, 0); b.pack_end(w, False, False, 0); return b
        self.src = label("", "summit-subtle")
        self.pack_start(card(section("Automatic updates"),
            row("Install updates automatically", "Checks every 6 hours and installs Summit updates in the background.", self.sw_auto),
            Gtk.Separator(),
            row("Live testing", "Checks every 2 minutes and installs every new change right away, refreshing the desktop without signing out. "
                "For trying out work in progress.", self.sw_live),
            self.src), False, False, 0)
        # --- history + system updates card
        self.hist = label("", "summit-subtle", markup=True)
        self.btn_back = Gtk.Button(label="Roll Back…"); self.btn_back.connect("clicked", self.on_rollback)
        sysb = Gtk.Button(label="Ubuntu System Updates…")
        sysb.connect("clicked", lambda *_: subprocess.Popen(["xfce4-terminal", "--title=System Updates", "-x", "sh", "-c",
                      "echo 'Checking Ubuntu for security and app updates…'; sudo apt update && sudo apt full-upgrade; echo; read -p 'Press Return to close.' x"]))
        logb = Gtk.Button(label="Show Log"); logb.connect("clicked", self.on_log)
        hb = Gtk.Box(spacing=8); hb.pack_start(self.btn_back, False, False, 0); hb.pack_start(sysb, False, False, 0); hb.pack_start(logb, False, False, 0)
        self.pack_start(card(section("History", "Undo the last update if something isn't right. Ubuntu security updates are separate."),
                             self.hist, hb), False, False, 0)
        self.refresh()
        self._timer = GLib.timeout_add_seconds(2, self.refresh)
        self.connect("destroy", lambda *_: GLib.source_remove(self._timer))

    def refresh(self):
        st, stat, av, c = upd_json("state.json"), upd_json("status.json"), upd_json("available.json"), upd_conf()
        ver = st.get("version") or next((l.split('"')[1].split()[2] for l in open("/etc/os-release") if l.startswith("PRETTY_NAME=")), "")
        busy = stat.get("state") in ("checking", "installing")
        self.spin.start() if busy else self.spin.stop(); self.spin.set_visible(busy)
        if stat.get("state") == "installing":
            self.title.set_text(stat.get("message", "Installing…")); self.sub.set_text("You can keep working.")
        elif av:
            self.title.set_text(f"Summit OS {av.get('version')} is available")
            self.sub.set_text(f"You have Summit OS {ver}.")
        elif stat.get("state") == "error":
            self.title.set_text(f"Summit OS {ver}"); self.sub.set_text(stat.get("message", "") + " " + (stat.get("error", "") or "")[:140])
        else:
            self.title.set_text(f"Summit OS {ver}")
            self.sub.set_text(("Up to date · " if stat.get("state") in ("idle", "installed") else "") + f"Last checked {ago(stat.get('last_check'))}")
        notes = av.get("notes") if av else st.get("notes")
        hdr = "What's new" if av else ("Installed " + ago(st.get("installed_at")) if st.get("installed_at") else "")
        self.notes.set_markup((f"<b>{hdr}</b>\n" + "\n".join("• " + GLib.markup_escape_text(n) for n in notes[:6])) if notes else "")
        self.notes.set_visible(bool(notes))
        self.btn_install.set_visible(bool(av) and not busy); self.btn_check.set_sensitive(not busy and bool(c.get("repo")))
        self._lock = True; self.sw_auto.set_active(bool(c.get("auto_install"))); self.sw_live.set_active(bool(c.get("live"))); self._lock = False
        self.src.set_text(f"Updates come from github.com/{c['repo']} ({c.get('branch','main')})." if c.get("repo")
                          else "No update source is set up yet.")
        backups = sorted(os.listdir(os.path.join(UPD, "backups"))) if os.path.isdir(os.path.join(UPD, "backups")) else []
        rb = st.get("rolled_back_from")
        lines = []
        if rb: lines.append(f"Rolled back from {GLib.markup_escape_text(str(rb.get('version')))}")
        lines.append(f"{len(backups)} earlier version{'s' if len(backups) != 1 else ''} saved for roll back")
        self.hist.set_markup("\n".join(lines))
        self.btn_back.set_sensitive(bool(backups) and not busy)
        return True

    def start_unit(self, unit):
        def work():
            r = sh("systemctl", "start", "--no-block", unit, timeout=20)
            if r.returncode != 0:
                sh("pkexec", "/usr/local/sbin/summit-update", "install" if "install" in unit else "check", timeout=900)
        threading.Thread(target=work, daemon=True).start()
    def on_check(self, _b): self.start_unit("summit-update-now.service")
    def on_install(self, _b): self.start_unit("summit-update-install.service")
    def on_switch(self, sw, _p, key):
        if self._lock: return
        def work():
            r = sh("pkexec", "/usr/local/sbin/summit-update", "set", f"{key}={'true' if sw.get_active() else 'false'}", timeout=120)
            if r.returncode == 0 and sw.get_active(): sh("systemctl", "start", "--no-block", "summit-update-now.service")
            GLib.idle_add(self.refresh)
        threading.Thread(target=work, daemon=True).start()
    def on_rollback(self, _b):
        st = upd_json("state.json")
        d = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.NONE, text=f"Undo the last update?")
        d.format_secondary_text(f"Summit will go back to the version before {st.get('version', 'this one')}. Your files and settings aren't affected.")
        d.add_button("Cancel", Gtk.ResponseType.CANCEL); d.add_button("Roll Back", Gtk.ResponseType.OK)
        r = d.run(); d.destroy()
        if r == Gtk.ResponseType.OK:
            threading.Thread(target=lambda: sh("pkexec", "/usr/local/sbin/summit-update", "rollback", timeout=600), daemon=True).start()
    def on_log(self, _b):
        txt = sh("summit-update", "log").stdout or "No activity yet."
        d = Gtk.Dialog(title="Software Update Log", transient_for=self.get_toplevel(), modal=True); d.add_button("Close", Gtk.ResponseType.CLOSE)
        d.set_default_size(720, 420)
        tv = Gtk.TextView(editable=False, monospace=True); tv.get_buffer().set_text(txt)
        sc = Gtk.ScrolledWindow(); sc.add(tv); d.get_content_area().pack_start(sc, True, True, 0); d.show_all(); d.run(); d.destroy()

# ======================================================================= About
MODELS = {"iMac14,4": "iMac (21.5-inch, Mid 2014)", "iMac14,1": "iMac (21.5-inch, Late 2013)", "iMac14,2": "iMac (27-inch, Late 2013)",
          "iMac15,1": "iMac (Retina 5K, 27-inch, Late 2014)", "iMac16,1": "iMac (21.5-inch, Late 2015)", "iMac16,2": "iMac (Retina 4K, 21.5-inch, Late 2015)"}
def read(p):
    try: return open(p).read().strip()
    except OSError: return ""

class AboutPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        logo = Gtk.Image.new_from_icon_name("summitos", Gtk.IconSize.DIALOG); logo.set_pixel_size(112)
        prod = read("/sys/class/dmi/id/product_name")
        model = MODELS.get(prod, prod or "Computer")
        cpu = next((l.split(":", 1)[1].strip() for l in read("/proc/cpuinfo").splitlines() if l.startswith("model name")), "")
        cpu = re.sub(r"\s+", " ", cpu.replace("(R)", "").replace("(TM)", "").replace("CPU ", ""))
        mem = next((int(l.split()[1]) for l in read("/proc/meminfo").splitlines() if l.startswith("MemTotal")), 0)
        gpu = ""
        r = sh("sh", "-c", "lspci 2>/dev/null | grep -iE 'vga|display' | head -1 | cut -d: -f3")
        gpu = (r.stdout or "").strip().replace("Intel Corporation ", "Intel ").replace("Corporation ", "")
        root = sh("findmnt", "-no", "SOURCE", "/").stdout.strip()
        disk = sh("sh", "-c", f"lsblk -no PKNAME {root} 2>/dev/null | head -1").stdout.strip()
        dmodel = sh("lsblk", "-dno", "MODEL", f"/dev/{disk}").stdout.strip() if disk else ""
        ver = next((l.split("=", 1)[1].strip('"') for l in read("/etc/os-release").splitlines() if l.startswith("PRETTY_NAME=")), "Summit OS")
        grid = Gtk.Grid(column_spacing=18, row_spacing=6, halign=Gtk.Align.CENTER)
        rows = [("Chip", cpu), ("Memory", f"{round(mem / 1048576)} GB"), ("Graphics", gpu or "Intel graphics"),
                ("Startup disk", dmodel or "—"), ("Name", f"{HOST}.local")]
        for i, (k, v) in enumerate(rows):
            grid.attach(label(k, "summit-subtle", xalign=1, wrap=False), 0, i, 1, 1)
            grid.attach(label(v, xalign=0), 1, i, 1, 1)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER)
        top.pack_start(logo, False, False, 6)
        top.pack_start(label(model, "summit-hero", xalign=0.5), False, False, 0)
        top.pack_start(label(ver, "summit-subtle", xalign=0.5), False, False, 0)
        btns = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        up = Gtk.Button(label="Software Update…")
        up.connect("clicked", lambda *_: self.get_toplevel().show_page("update"))
        mon = Gtk.Button(label="Activity…"); mon.connect("clicked", lambda *_: subprocess.Popen(["xfce4-taskmanager"]))
        btns.pack_start(up, False, False, 0); btns.pack_start(mon, False, False, 0)
        self.pack_start(card(top, grid, btns, spacing=14), False, False, 0)

# ======================================================================= window
MORE = [("Displays", "preferences-desktop-display", ["xfce4-display-settings"]),
        ("Sound", "multimedia-volume-control", ["pavucontrol"]),
        ("Network", "preferences-system-network", ["nm-connection-editor"]),
        ("Keyboard", "preferences-desktop-keyboard", ["xfce4-keyboard-settings"]),
        ("Power & Screen Saver", "preferences-system-power", ["xfce4-power-manager-settings"]),
        ("All Settings", "preferences-system", ["xfce4-settings-manager"])]

class Settings(Gtk.Window):
    PAGES = [("appearance", "Appearance", "preferences-desktop-theme"), ("storage", "Storage", "drive-harddisk"),
             ("mouse", "Mouse & Trackpad", "preferences-desktop-peripherals"),
             ("sharing", "Sharing", "folder-remote"), ("bluetooth", "Bluetooth", "bluetooth"),
             ("update", "Software Update", "summit-update"),
             ("about", "About This iMac", "summitos")]
    def __init__(self, page="appearance"):
        super().__init__(title="Settings")
        self.set_wmclass("summit-settings", "Summit-settings")
        self.set_default_size(940, 660); self.set_icon_name("summit-settings"); self.set_position(Gtk.WindowPosition.CENTER)
        hb = Gtk.Box()
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); side.get_style_context().add_class("summit-sidebar")
        side.set_size_request(230, -1)
        self.lb = Gtk.ListBox(); self.lb.get_style_context().add_class("summit-sidebar")
        self.lb.set_margin_top(14)
        for key, name, icon in self.PAGES:
            self.lb.add(self.side_row(name, icon, key))
        self.lb.connect("row-selected", self.on_row)
        side.pack_start(self.lb, False, False, 0)
        more_hdr = label("<small><b>MORE</b></small>", "summit-subtle", markup=True)
        more_hdr.set_margin_start(20); more_hdr.set_margin_top(16); more_hdr.set_margin_bottom(4)
        side.pack_start(more_hdr, False, False, 0)
        self.more = Gtk.ListBox(); self.more.get_style_context().add_class("summit-sidebar")
        for name, icon, cmd in MORE:
            r = self.side_row(name, icon, None); r.cmd = cmd; self.more.add(r)
        self.more.connect("row-activated", lambda lb, r: (subprocess.Popen(r.cmd), lb.unselect_all()))
        side.pack_start(self.more, False, False, 0)
        hb.pack_start(side, False, False, 0)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=150)
        self.built = {}
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); sc.add(self.stack)
        hb.pack_start(sc, True, True, 0); self.add(hb)
        keys = [p[0] for p in self.PAGES]
        self.lb.select_row(self.lb.get_row_at_index(keys.index(page) if page in keys else 0))

    def side_row(self, name, icon, key):
        r = Gtk.ListBoxRow(); r.key = key
        b = Gtk.Box(spacing=10)
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR); img.set_pixel_size(22)
        b.pack_start(img, False, False, 0); b.pack_start(label(name, wrap=False), False, False, 0)
        r.add(b); return r

    def show_page(self, key):
        for r in self.lb.get_children():
            if getattr(r, "key", None) == key: self.lb.select_row(r); return

    def on_row(self, _lb, row):
        if not row: return
        k = row.key
        if k not in self.built:
            if k == "bluetooth":
                import summit_bluetooth; page = summit_bluetooth.BluetoothPage()      # loaded only when opened
            else:
                page = {"appearance": AppearancePage, "storage": StoragePage, "mouse": MousePage, "sharing": SharingPage, "update": UpdatePage, "about": AboutPage}[k]()
            wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); wrap.set_margin_start(28); wrap.set_margin_end(28); wrap.set_margin_top(22)
            wrap.pack_start(page, False, False, 0)
            self.stack.add_named(wrap, k); wrap.show_all(); self.built[k] = wrap
        self.stack.set_visible_child_name(k)

# ======================================================================= Welcome
class Welcome(Gtk.Window):
    def __init__(self):
        super().__init__(title="Welcome to Summit")
        self.set_wmclass("summit-settings", "Summit-settings")
        self.set_default_size(760, 600); self.set_position(Gtk.WindowPosition.CENTER); self.set_icon_name("summitos")
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=250)
        steps = [self.hello(), self.look()]
        hdd = [d for d in disks() if "/" not in d["all_mounts"] and d.get("tran") != "usb" and "iMac HD" not in d["labels"]]
        if hdd and not LIVE: steps.append(self.storage())
        steps.append(self.done())
        self.steps = steps
        for i, s in enumerate(steps): self.stack.add_named(s, str(i))
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.pack_start(self.stack, True, True, 0)
        nav = Gtk.Box(spacing=8, margin=18)
        self.dots = label("", "summit-subtle", wrap=False)
        self.back = Gtk.Button(label="Back"); self.back.connect("clicked", lambda *_: self.go(-1))
        self.next = Gtk.Button(label="Continue"); self.next.get_style_context().add_class("suggested-action"); self.next.connect("clicked", lambda *_: self.go(1))
        nav.pack_start(self.dots, False, False, 0); nav.pack_end(self.next, False, False, 0); nav.pack_end(self.back, False, False, 0)
        outer.pack_end(nav, False, False, 0)
        self.add(outer); self.i = 0; self.update()
        # closing the window counts as finishing, so it doesn't come back at every login
        self.connect("delete-event", lambda *_: (self.mark_done(), False)[1])

    def page(self, *widgets):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=36, valign=Gtk.Align.CENTER)
        for w in widgets: b.pack_start(w, False, False, 0)
        return b
    def hello(self):
        logo = Gtk.Image.new_from_icon_name("summitos", Gtk.IconSize.DIALOG); logo.set_pixel_size(128)
        return self.page(logo, label("Welcome to Summit", "summit-hero", xalign=0.5),
                         label("Let's make this iMac yours. It takes less than a minute.", "summit-subtle", xalign=0.5))
    def look(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        b.pack_start(label("Choose your look", "summit-hero"), False, False, 8)
        b.pack_start(AppearancePage(compact=True), False, False, 0)
        b.set_margin_start(36); b.set_margin_end(36); b.set_margin_top(28)
        return b
    def storage(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        b.pack_start(label("Your internal hard drive", "summit-hero"), False, False, 8)
        b.pack_start(label("Summit runs from your SSD. Your iMac's internal hard drive can become “iMac HD” for "
                           "Documents, Downloads, Pictures, Music, Videos and Time Machine backups. You can also do this later "
                           "in Settings → Storage.", "summit-subtle"), False, False, 6)
        b.pack_start(StoragePage(header=False), False, False, 0)
        b.set_margin_start(36); b.set_margin_end(36); b.set_margin_top(28)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); sc.add(b); return sc
    def done(self):
        tips = label("<b>⌘ Space</b>  Spotlight search\n<b>⌘ A</b>  Launchpad, all your apps\n"
                     "<b>Control Center</b>  the switches icon in the menu bar\n<b>Settings</b>  the gear in the dock",
                     xalign=0.5, markup=True)
        return self.page(label("You're all set", "summit-hero", xalign=0.5), tips)
    def go(self, d):
        if self.i + d >= len(self.steps): self.finish(); return
        self.i = max(0, self.i + d); self.update()
    def update(self):
        self.stack.set_visible_child_name(str(self.i))
        self.back.set_sensitive(self.i > 0)
        self.next.set_label("Get Started" if self.i == len(self.steps) - 1 else "Continue")
        self.dots.set_text("  ".join("●" if k == self.i else "○" for k in range(len(self.steps))))
    def mark_done(self):
        os.makedirs(CFG, exist_ok=True); open(os.path.join(CFG, "welcome-done"), "w").close()
    def finish(self):
        self.mark_done(); self.destroy()

def main():
    args = sys.argv[1:]
    if "--welcome" in args:
        if os.path.exists(os.path.join(CFG, "welcome-done")) and "--force" not in args: return
        w = Welcome()
    else:
        page = args[args.index("--page") + 1] if "--page" in args and len(args) > args.index("--page") + 1 else "appearance"
        w = Settings(page)
    watch_css()
    w.connect("destroy", Gtk.main_quit); w.show_all(); Gtk.main()

if __name__ == "__main__":
    main()
