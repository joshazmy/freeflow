"""About pane — wordmark, version, credits (mockup #pane-about)."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from freeflow import __version__


def _row(label: str, value: str) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.append(Gtk.Label(label=label, xalign=0, hexpand=True))
    val = Gtk.Label(label=value, xalign=1)
    val.add_css_class("ff-mono")
    box.append(val)
    return box


def build(ctx) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_margin_top(12)
    box.set_margin_bottom(12)
    box.set_margin_start(12)
    box.set_margin_end(12)

    title = Gtk.Label(label="Freeflow", xalign=0)
    title.add_css_class("ff-serif")
    title.add_css_class("title-2")
    box.append(title)

    subtitle = Gtk.Label(label=f"v{__version__} · MIT License", xalign=0)
    subtitle.add_css_class("ff-muted")
    box.append(subtitle)

    box.append(_row("Source", "github.com/joshazmy/freeflow"))
    box.append(_row("Speech engine", "whisper.cpp"))
    box.append(_row("Cleanup engine", "Ollama"))

    return box
