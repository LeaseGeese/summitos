"""summit_bluetooth: the Bluetooth page of Summit Settings.

One "Connect" button does everything a mouse, keyboard, trackpad or headphones needs: pair, trust
(so the device may reconnect by itself after sleep or a restart) and connect. It speaks to the system
Bluetooth service (BlueZ) directly and answers its pairing questions itself, so no other Bluetooth
helper has to be running. Searching for devices only happens while this page is on screen.
"""
import os, random, subprocess
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib, Pango

BLUEZ = "org.bluez"
ADAPTER, DEVICE, PROPS, OM = "org.bluez.Adapter1", "org.bluez.Device1", "org.freedesktop.DBus.Properties", "org.freedesktop.DBus.ObjectManager"
AGENT_PATH = "/org/summitos/BluetoothAgent"
AGENT_XML = """<node><interface name="org.bluez.Agent1">
<method name="Release"/>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="Cancel"/>
</interface></node>"""
NOISY = {"RSSI", "TxPower", "ManufacturerData", "ServiceData", "AdvertisingFlags", "AdvertisingData"}   # change constantly while searching
ICONS = {"input-mouse": "input-mouse", "input-keyboard": "input-keyboard", "input-tablet": "input-tablet",
         "input-gaming": "input-gaming", "audio-headset": "audio-headphones", "audio-headphones": "audio-headphones",
         "audio-card": "audio-speakers", "phone": "phone", "computer": "computer", "printer": "printer"}

def label(text, cls=None, xalign=0, wrap=True):
    l = Gtk.Label(label=text, xalign=xalign, wrap=wrap); l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    for c in (cls.split() if cls else []): l.get_style_context().add_class(c)
    return l

def title(text):
    l = Gtk.Label(xalign=0); l.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>"); return l

def card(*children):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); b.get_style_context().add_class("summit-card"); b.set_margin_bottom(14)
    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
    for c in children: inner.pack_start(c, False, False, 0)
    b.pack_start(inner, True, True, 0)
    return b

def explain(err, name, paired):
    """A BlueZ error in plain words."""
    m = (err.message if err else "").lower()
    if "authentication" in m or "rejected" in m or "key missing" in m:
        if paired: return (f"{name} didn't accept the saved pairing. It was probably paired with another computer since. "
                           "Click Pair Again.")
        return f"{name} refused to pair. Turn it off and on again, then click Connect while its light is blinking."
    if "page-timeout" in m or "host is down" in m or "timeout" in m or "connection-attempt" in m or "not available" in m or "abort" in m:
        return (f"Couldn't reach {name}. Make sure it's switched on and close by. If it's also paired with another Mac, "
                "turn Bluetooth off on that Mac (or choose Forget This Device there): it connects to that Mac first.")
    if "in progress" in m or "inprogress" in m or "busy" in m:
        return f"Still working on {name}. Give it a few seconds and try again."
    if "profile-unavailable" in m or "not supported" in m:
        return f"{name} is paired, but it offers nothing this iMac can connect to right now. Turn it off and on again."
    short = (err.message.split(":")[-1].strip() if err else "unknown error")
    return f"Couldn't connect to {name} ({short}). Turn it off and on again and retry."

class BluetoothPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.objs = {}; self.adapter = None; self.busy = {}; self.pairing = None; self.repair = None
        self.subs = []; self.agent_id = None; self.refresh_id = None; self.searching = False; self.bus = None
        head = Gtk.Box(spacing=12)
        t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        t.pack_start(label("Bluetooth", "summit-hero"), False, False, 0)
        self.status = label("", "summit-subtle"); t.pack_start(self.status, False, False, 0)
        head.pack_start(t, True, True, 0)
        self.spin = Gtk.Spinner(valign=Gtk.Align.CENTER); head.pack_start(self.spin, False, False, 0)
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER); self.switch_handler = self.switch.connect("state-set", self.on_switch)
        head.pack_start(self.switch, False, False, 0)
        self.pack_start(card(head), False, False, 0)
        self.note = Gtk.InfoBar(); self.note.set_no_show_all(True); self.note.set_show_close_button(True)
        self.note_label = label(""); self.note.get_content_area().add(self.note_label); self.note_label.show()
        self.note.connect("response", lambda *_: self.note.hide()); self.note.set_margin_bottom(14)
        self.pack_start(self.note, False, False, 0)
        self.mine_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.near_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.mine_card = card(title("My Devices"), self.mine_box)
        self.near_card = card(title("Nearby Devices"), self.near_box,
                              label("Not listed? Switch the device off and on so its light blinks. A mouse or keyboard that is "
                                    "paired with another Mac connects to that Mac first: turn Bluetooth off there, or choose "
                                    "Forget This Device.", "summit-subtle"))
        self.pack_start(self.mine_card, False, False, 0); self.pack_start(self.near_card, False, False, 0)
        adv = Gtk.Button(label="Advanced…", halign=Gtk.Align.START)
        adv.connect("clicked", lambda *_: subprocess.Popen(["blueman-manager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.pack_start(adv, False, False, 0)
        self.connect("map", lambda *_: self.start()); self.connect("unmap", lambda *_: self.search(False))
        self.connect("destroy", lambda *_: self.stop())

    # ---- talking to BlueZ
    def call(self, path, iface, method, args=None, cb=None, timeout=30000):
        def done(src, res):
            err = None
            try: src.call_finish(res)
            except GLib.Error as e: err = e
            if cb: cb(err)
        self.bus.call(BLUEZ, path, iface, method, args, None, Gio.DBusCallFlags.NONE, timeout, None, done)

    def set_prop(self, path, iface, name, value, cb=None):
        self.call(path, PROPS, "Set", GLib.Variant("(ssv)", (iface, name, value)), cb)

    def start(self):
        if self.bus is None:
            try: self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            except GLib.Error: self.status.set_text("The system's message bus isn't available."); return
            sub = self.bus.signal_subscribe
            self.subs = [sub(BLUEZ, OM, "InterfacesAdded", None, None, Gio.DBusSignalFlags.NONE, self.on_added),
                         sub(BLUEZ, OM, "InterfacesRemoved", None, None, Gio.DBusSignalFlags.NONE, self.on_removed),
                         sub(BLUEZ, PROPS, "PropertiesChanged", None, None, Gio.DBusSignalFlags.NONE, self.on_changed)]
            self.watch = Gio.bus_watch_name_on_connection(self.bus, BLUEZ, Gio.BusNameWatcherFlags.NONE,
                                                         lambda *_: self.load(), lambda *_: self.load())
            node = Gio.DBusNodeInfo.new_for_xml(AGENT_XML)
            try:
                self.agent_id = self.bus.register_object(AGENT_PATH, node.interfaces[0], self.on_agent, None, None)
            except GLib.Error:
                self.agent_id = None
        else:
            self.load()

    def load(self):
        try:
            r = self.bus.call_sync(BLUEZ, "/", OM, "GetManagedObjects", None, GLib.VariantType("(a{oa{sa{sv}}})"),
                                   Gio.DBusCallFlags.NONE, 4000, None)
            self.objs = r.unpack()[0]
        except GLib.Error:
            self.objs = {}
        self.adapter = next((p for p, i in sorted(self.objs.items()) if ADAPTER in i), None)
        if self.adapter and self.agent_id:
            self.call("/org/bluez", "org.bluez.AgentManager1", "RegisterAgent", GLib.Variant("(os)", (AGENT_PATH, "KeyboardDisplay")),
                      lambda e: self.call("/org/bluez", "org.bluez.AgentManager1", "RequestDefaultAgent", GLib.Variant("(o)", (AGENT_PATH,))))
        self.searching = False
        self.render()
        if self.get_mapped(): self.search(True)

    def stop(self):
        if self.bus is None: return
        self.search(False)
        for s in self.subs: self.bus.signal_unsubscribe(s)
        Gio.bus_unwatch_name(self.watch)
        if self.agent_id:
            self.bus.unregister_object(self.agent_id)
            self.bus.call(BLUEZ, "/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent", GLib.Variant("(o)", (AGENT_PATH,)),
                          None, Gio.DBusCallFlags.NONE, 2000, None, None)
        self.bus = None

    def powered(self):
        return bool(self.adapter and self.objs.get(self.adapter, {}).get(ADAPTER, {}).get("Powered"))

    def search(self, on):
        if not self.adapter or self.bus is None: return
        if on and self.powered() and not self.searching and not self.pairing:
            self.searching = True; self.call(self.adapter, ADAPTER, "StartDiscovery", cb=lambda e: self.render())
        elif not on and self.searching:
            self.searching = False; self.call(self.adapter, ADAPTER, "StopDiscovery")

    # ---- changes from BlueZ
    def on_added(self, _c, _s, _p, _i, _sig, params):
        path, ifaces = params.unpack(); self.objs.setdefault(path, {}).update(ifaces)
        if ADAPTER in ifaces and not self.adapter: self.load(); return
        d = ifaces.get(DEVICE)
        if d and self.repair and d.get("Address") == self.repair and not self.pairing:
            self.repair = None; GLib.timeout_add(600, lambda: (self.connect_device(path), False)[1])
        self.later()
    def on_removed(self, _c, _s, _p, _i, _sig, params):
        path, ifaces = params.unpack()
        for i in ifaces: self.objs.get(path, {}).pop(i, None)
        if not self.objs.get(path): self.objs.pop(path, None)
        if path == self.adapter: self.load(); return
        self.later()
    def on_changed(self, _c, _s, path, _i, _sig, params):
        iface, changed, _inv = params.unpack()
        if path not in self.objs: return
        self.objs[path].setdefault(iface, {}).update(changed)
        if set(changed) - NOISY: self.later()
    def later(self):
        if self.refresh_id is None: self.refresh_id = GLib.timeout_add(200, self.render)

    # ---- the page
    def say(self, text, kind=Gtk.MessageType.INFO):
        self.note_label.set_text(text); self.note.set_message_type(kind); self.note.show()

    def render(self):
        self.refresh_id = None
        if not self.get_mapped() and not self.pairing: return False
        on = self.powered()
        self.switch.handler_block(self.switch_handler); self.switch.set_state(on); self.switch.set_active(on)
        self.switch.set_sensitive(bool(self.adapter)); self.switch.handler_unblock(self.switch_handler)
        if not self.adapter:
            self.status.set_text("No Bluetooth hardware was found. If this iMac has just started, wait a moment.")
        elif not on: self.status.set_text("Off")
        else: self.status.set_text("On. Looking for devices while this page is open…" if self.searching else "On")
        (self.spin.start if on and (self.searching or self.busy) else self.spin.stop)()
        devs = [(p, i[DEVICE]) for p, i in self.objs.items() if DEVICE in i and p.startswith((self.adapter or "-") + "/")]
        mine = sorted((d for d in devs if d[1].get("Paired")), key=lambda d: (not d[1].get("Connected"), d[1].get("Alias", "")))
        near = sorted((d for d in devs if not d[1].get("Paired") and d[1].get("Name")), key=lambda d: -d[1].get("RSSI", -200))[:12]
        for box, items in ((self.mine_box, mine), (self.near_box, near)):
            for c in box.get_children(): box.remove(c); c.destroy()
            for path, d in items: box.pack_start(self.row(path, d), False, False, 0)
        if not mine: self.mine_box.pack_start(label("No devices yet.", "summit-subtle"), False, False, 0)
        if not near: self.near_box.pack_start(label(("Searching…" if self.searching else "Nothing new nearby.") if on else "Turn Bluetooth on to look for devices.", "summit-subtle"), False, False, 0)
        self.mine_card.set_visible(bool(self.adapter)); self.near_card.set_visible(bool(self.adapter))
        self.mine_box.show_all(); self.near_box.show_all()
        return False

    def battery(self, d):
        try:
            with open(f"/sys/class/power_supply/hid-{d.get('Address', '').lower()}-battery/capacity") as f: return f"{int(f.read())}%"
        except (OSError, ValueError):
            return None

    def row(self, path, d):
        name = d.get("Alias") or d.get("Name") or d.get("Address", "Device")
        b = Gtk.Box(spacing=12)
        img = Gtk.Image.new_from_icon_name(ICONS.get(d.get("Icon"), "bluetooth"), Gtk.IconSize.DND); img.set_pixel_size(28)
        b.pack_start(img, False, False, 0)
        t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        t.pack_start(label(name, wrap=False), False, False, 0)
        if path in self.busy: sub = self.busy[path]
        elif d.get("Connected"):
            bat = self.battery(d); sub = "Connected" + (f"  ·  Battery {bat}" if bat else "")
        else: sub = "Not connected" if d.get("Paired") else ""
        if sub: t.pack_start(label(sub, "summit-subtle", wrap=False), False, False, 0)
        b.pack_start(t, True, True, 0)
        if path in self.busy:
            return b
        if d.get("Paired"):
            f = Gtk.Button(label="Forget"); f.connect("clicked", lambda *_: self.forget(path, name)); b.pack_end(f, False, False, 0)
            if d.get("Connected"):
                c = Gtk.Button(label="Disconnect"); c.connect("clicked", lambda *_: self.call(path, DEVICE, "Disconnect"))
            else:
                a = Gtk.Button(label="Pair Again"); a.set_tooltip_text("Use this if the device was paired with another computer since")
                a.connect("clicked", lambda *_: self.pair_again(path, d)); b.pack_end(a, False, False, 0)
                c = Gtk.Button(label="Connect"); c.get_style_context().add_class("suggested-action")
                c.connect("clicked", lambda *_: self.connect_device(path))
            b.pack_end(c, False, False, 0)
        else:
            c = Gtk.Button(label="Connect"); c.get_style_context().add_class("suggested-action")
            c.connect("clicked", lambda *_: self.connect_device(path)); b.pack_end(c, False, False, 0)
        return b

    # ---- actions
    def on_switch(self, _sw, state):
        if not self.adapter: return True
        def done(err):
            if err and state:      # usually "blocked": the wireless switch is off. Unblock and try once more.
                subprocess.run(["rfkill", "unblock", "bluetooth"], capture_output=True)
                self.set_prop(self.adapter, ADAPTER, "Powered", GLib.Variant("b", True), lambda e: (e and self.say(
                    "Bluetooth couldn't be turned on. Restart the iMac and try again.", Gtk.MessageType.WARNING), self.after_power()))
            else: self.after_power()
        self.set_prop(self.adapter, ADAPTER, "Powered", GLib.Variant("b", bool(state)), done)
        return True
    def after_power(self):
        GLib.timeout_add(700, lambda: (self.search(True), self.render(), False)[2])

    def name_of(self, path):
        d = self.objs.get(path, {}).get(DEVICE, {})
        return d.get("Alias") or d.get("Name") or "the device"

    def finish(self, path, text=None, kind=Gtk.MessageType.INFO):
        self.busy.pop(path, None)
        if self.pairing == path: self.pairing = None
        if text: self.say(text, kind)
        else: self.note.hide()
        self.render()
        if self.get_mapped(): self.search(True)

    def connect_device(self, path):
        d = self.objs.get(path, {}).get(DEVICE)
        if d is None or path in self.busy: return
        name = self.name_of(path); self.note.hide()
        self.search(False)                       # searching and connecting at once makes both unreliable
        self.pairing = path
        def trusted(_e=None):
            self.busy[path] = "Connecting…"; self.render()
            self.call(path, DEVICE, "Connect", cb=connected, timeout=45000)
        def connected(err):
            # mice and keyboards often connect by themselves right after pairing: judge by the result, a moment later
            def check():
                now = self.objs.get(path, {}).get(DEVICE, {})
                if now.get("Connected"):
                    extra = "" if "magic" not in name.lower() else "  Gestures are on: swipe with one or two fingers."
                    self.finish(path, f"{name} is connected and will reconnect by itself from now on." + extra)
                else:
                    self.finish(path, explain(err, name, True), Gtk.MessageType.WARNING)
                return False
            GLib.timeout_add(2500 if err else 300, check)
        def paired(err):
            if err and "alreadyexists" not in err.message.lower().replace(" ", ""):
                self.finish(path, explain(err, name, False), Gtk.MessageType.WARNING); return
            self.set_prop(path, DEVICE, "Trusted", GLib.Variant("b", True), trusted)
        if d.get("Paired"):
            self.set_prop(path, DEVICE, "Trusted", GLib.Variant("b", True), trusted)
        else:
            self.busy[path] = "Pairing…"; self.render()
            self.call(path, DEVICE, "Pair", cb=paired, timeout=90000)

    def forget(self, path, name):
        if self.adapter: self.call(self.adapter, ADAPTER, "RemoveDevice", GLib.Variant("(o)", (path,)), lambda e: self.render())

    def pair_again(self, path, d):
        """Drop the saved pairing, then pair afresh as soon as the device shows up again."""
        addr, name = d.get("Address"), self.name_of(path)
        self.repair = addr
        self.say(f"Now switch {name} off and on, so its light blinks. It will be paired as soon as it appears.")
        def removed(_e):
            self.search(True)
            GLib.timeout_add_seconds(60, lambda: (setattr(self, "repair", None) if self.repair == addr else None, False)[1])
        self.call(self.adapter, ADAPTER, "RemoveDevice", GLib.Variant("(o)", (path,)), removed)

    # ---- pairing questions from BlueZ
    def ours(self, path):
        d = self.objs.get(path, {}).get(DEVICE, {})
        return path == self.pairing or d.get("Paired") or d.get("Trusted")

    def ask(self, text):
        dlg = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True, message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.NONE, text=text)
        dlg.add_button("Don't Allow", Gtk.ResponseType.NO); dlg.add_button("Allow", Gtk.ResponseType.YES)
        r = dlg.run(); dlg.destroy()
        return r == Gtk.ResponseType.YES

    def on_agent(self, _conn, _sender, _path, _iface, method, params, inv):
        args = params.unpack(); dev = args[0] if args else None
        name = self.name_of(dev) if dev else "A device"
        d = self.objs.get(dev, {}).get(DEVICE, {}) if dev else {}
        reject = lambda: inv.return_dbus_error("org.bluez.Error.Rejected", "Not allowed")
        if method == "RequestPinCode":
            pointing = d.get("Icon") in ("input-mouse", "input-tablet") or any(w in name.lower() for w in ("mouse", "trackpad"))
            if pointing: pin = "0000"                                    # what mice without keys expect
            else:
                pin = f"{random.randrange(1000000):06d}"
                self.say(f"On {name}, type {pin} and press Return.")
            inv.return_value(GLib.Variant("(s)", (pin,)))
        elif method in ("DisplayPinCode", "DisplayPasskey"):
            code = args[1] if method == "DisplayPinCode" else f"{args[1]:06d}"
            self.say(f"On {name}, type {code} and press Return."); inv.return_value(None)
        elif method == "RequestConfirmation":
            if self.ours(dev): self.say(f"Pairing with {name} (code {args[1]:06d})…"); inv.return_value(None)
            elif self.ask(f"Pair with {name}? It shows the code {args[1]:06d}."): inv.return_value(None)
            else: reject()
        elif method in ("RequestAuthorization", "AuthorizeService"):
            if self.ours(dev) or self.ask(f"Allow {name} to connect to this iMac?"): inv.return_value(None)
            else: reject()
        elif method == "RequestPasskey":
            reject()
        else:                                                              # Release, Cancel
            inv.return_value(None)
