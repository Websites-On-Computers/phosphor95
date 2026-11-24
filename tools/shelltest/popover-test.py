#!/usr/bin/env python3
"""Test window for the harness: a libadwaita header bar whose ☰ menu pops open on map,
so menu-in-headerbar colours can be checked (the Ghostty / Files main-menu case)."""
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

def activate(app):
    win = Adw.ApplicationWindow(application=app, title="Popover test", default_width=520, default_height=360)
    menu = Gio.Menu()
    for label in ("New Window", "New Tab", "Split Right", "Preferences", "About Ghostty"):
        menu.append(label, "app.noop")
    btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
    hb = Adw.HeaderBar(); hb.pack_end(btn)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=16, margin_start=16)
    body.append(Gtk.Label(label="Label text  0123456789  The quick brown fox", xalign=0))
    body.append(Gtk.Button(label="Push button"))
    body.append(Gtk.Entry(text="entry text"))
    tv = Adw.ToolbarView(); tv.add_top_bar(hb); tv.set_content(body)
    win.set_content(tv); win.present()
    app.add_action(Gio.SimpleAction(name="noop"))
    GLib.timeout_add(1500, lambda: (btn.popup(), False)[1])

app = Adw.Application(application_id="org.p95.PopoverTest")
app.connect("activate", activate); app.run(None)
