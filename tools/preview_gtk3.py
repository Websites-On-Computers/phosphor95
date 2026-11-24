#!/usr/bin/env python3
"""Render a GTK3 widget gallery offscreen with a theme from build/ -> PNG.
usage: preview_gtk3.py OUT.png [--backdrop]
Run via ./phosphor preview gtk (sets XDG_DATA_HOME so build/gtk is found)."""
import sys
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # noqa: E402

out = sys.argv[1]
s = Gtk.Settings.get_default()
s.set_property("gtk-theme-name", "Phosphor95")
s.set_property("gtk-font-name", "W95FA 12")
# the session's gsettings font wins over Gtk.Settings on Wayland; force it for the preview
from gi.repository import Gdk  # noqa: E402
_css = Gtk.CssProvider(); _css.load_from_data(b"* { font-family: W95FA; font-size: 12pt; }")
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), _css, 600)

win = Gtk.OffscreenWindow()
outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
hb = Gtk.HeaderBar(title="SYS.TERMINAL - Properties", subtitle="TERMINAL-01")
hb.set_show_close_button(True)
hb.pack_start(Gtk.Button(label="Back"))
outer.pack_start(hb, False, False, 0)
mb = Gtk.MenuBar()
for name in ("File", "Edit", "View", "Help"):
    mb.append(Gtk.MenuItem(label=name))
outer.pack_start(mb, False, False, 0)

nb = Gtk.Notebook()
grid = Gtk.Grid(column_spacing=12, row_spacing=10, margin=14)
grid.attach(Gtk.Label(label="Model endpoint:", xalign=0), 0, 0, 1, 1)
e = Gtk.Entry(text="http://localhost:11434"); grid.attach(e, 1, 0, 2, 1)
grid.attach(Gtk.Label(label="Temperature:", xalign=0), 0, 1, 1, 1)
sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1); sc.set_value(62); sc.set_hexpand(True)
grid.attach(sc, 1, 1, 2, 1)
cb = Gtk.ComboBoxText(); [cb.append_text(t) for t in ("local/qwen", "claude", "llama")]; cb.set_active(0)
grid.attach(Gtk.Label(label="Engine:", xalign=0), 0, 2, 1, 1); grid.attach(cb, 1, 2, 1, 1)
grid.attach(Gtk.SpinButton.new_with_range(0, 4096, 1), 2, 2, 1, 1)
c1 = Gtk.CheckButton(label="Stream tokens"); c1.set_active(True)
c2 = Gtk.CheckButton(label="Log to disk")
r1 = Gtk.RadioButton(label="Voice"); r2 = Gtk.RadioButton.new_with_label_from_widget(r1, "Text"); r2.set_active(True)
dis = Gtk.CheckButton(label="Disabled option"); dis.set_sensitive(False); dis.set_active(True)
for i, w in enumerate((c1, c2, dis)):
    grid.attach(w, 0, 3 + i, 1, 1)
grid.attach(r1, 1, 3, 1, 1); grid.attach(r2, 1, 4, 1, 1)
sw = Gtk.Switch(); sw.set_active(True); sw.set_halign(Gtk.Align.START); grid.attach(sw, 2, 3, 1, 1)
pb = Gtk.ProgressBar(fraction=0.62, show_text=True, text="UPLINK 62%"); grid.attach(pb, 0, 6, 3, 1)
store = Gtk.ListStore(str, str)
for row in (("qwen2.5-7b", "ONLINE"), ("llama3-8b", "STANDBY"), ("claude", "REMOTE"), ("phi-3", "OFFLINE")):
    store.append(row)
tv = Gtk.TreeView(model=store)
for i, t in enumerate(("Model", "State")):
    tv.append_column(Gtk.TreeViewColumn(t, Gtk.CellRendererText(), text=i))
tv.get_selection().select_path(Gtk.TreePath(1))
fr = Gtk.Frame(label="Models"); sw2 = Gtk.ScrolledWindow(); sw2.set_size_request(-1, 110); sw2.add(tv); fr.add(sw2)
grid.attach(fr, 0, 7, 3, 1)
bb = Gtk.Box(spacing=8, halign=Gtk.Align.END)
ok = Gtk.Button(label="OK"); ok.get_style_context().add_class("suggested-action")
bb.pack_start(ok, False, False, 0); bb.pack_start(Gtk.Button(label="Cancel"), False, False, 0)
tb = Gtk.ToggleButton(label="Apply"); tb.set_active(True); bb.pack_start(tb, False, False, 0)
d = Gtk.Button(label="Disabled"); d.set_sensitive(False); bb.pack_start(d, False, False, 0)
grid.attach(bb, 0, 8, 3, 1)
nb.append_page(grid, Gtk.Label(label="General"))
nb.append_page(Gtk.Label(label="x"), Gtk.Label(label="Network"))
nb.append_page(Gtk.Label(label="x"), Gtk.Label(label="Display"))
outer.pack_start(nb, True, True, 0)
win.add(outer)
win.set_default_size(560, 600)
win.show_all()
if "--backdrop" in sys.argv:
    win.set_state_flags(Gtk.StateFlags.BACKDROP, False)


def snap():
    pb_ = win.get_pixbuf()
    pb_.savev(out, "png", [], [])
    Gtk.main_quit()
    return False


GLib.timeout_add(400, snap)
Gtk.main()
