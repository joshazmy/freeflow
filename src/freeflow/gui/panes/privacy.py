"""Data & Privacy pane — static, no config reads (mockup #pane-privacy)."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

CHECKS = (
    "Audio never leaves this machine",
    "No accounts, no sign-in",
    "No telemetry, ever",
    "Works fully offline",
)


def build(ctx) -> Gtk.Widget:
    panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    panel.add_css_class("ff-card")
    panel.set_margin_top(12)
    panel.set_margin_bottom(12)
    panel.set_margin_start(12)
    panel.set_margin_end(12)

    headline = Gtk.Label(label="100% local.", xalign=0)
    headline.add_css_class("ff-serif")
    headline.add_css_class("title-2")
    panel.append(headline)

    for text in CHECKS:
        row = Gtk.Label(label=f"✓  {text}", xalign=0)
        panel.append(row)

    chip = Gtk.Label(label="$ freeflow status ● all local")
    chip.add_css_class("ff-mono")
    panel.append(chip)

    return panel
