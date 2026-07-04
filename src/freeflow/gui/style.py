"""Freeflow GTK4 stylesheet — Wispr Flow visual language (design/mockup.html).

Shared CSS classes other pane modules should use:
  .ff-card          white card: 1px ink border, radius 20px, hard shadow
  .ff-pill          pill button/row: radius 999px, 1px ink border, cream bg
  .ff-pill-active   active/selected pill or sidebar row: lavender bg + ink border
  .ff-serif         display serif heading (Sentient/P052/Georgia)
  .ff-muted         secondary/caption text (dimmed ink)
  .ff-danger        destructive text/button accents (quit, remove, offline)
  .ff-mono          monospace chip (e.g. `$ freeflow status`)

Window/app chrome uses plain widget selectors (window, list, listboxrow) so this
file is the single source of truth for color tokens; pane modules only need the
class names above.
"""
from __future__ import annotations

CREAM = "#FFFEF0"
INK = "#111110"
LAVENDER = "#E7D4F9"

CSS = f"""
window {{
    background-color: {CREAM};
    color: {INK};
    font-family: "General Sans", "Inter", "Cantarell", sans-serif;
}}

.ff-serif {{
    font-family: "Sentient", "P052", "Georgia", serif;
}}

.ff-muted {{
    opacity: 0.6;
    font-size: 90%;
}}

.ff-danger {{
    color: #a33333;
}}

.ff-mono {{
    font-family: monospace;
    background-color: {LAVENDER};
    border: 1px solid {INK};
    border-radius: 999px;
    padding: 6px 14px;
}}

.ff-card {{
    background-color: #FFFFFF;
    border: 1px solid {INK};
    border-radius: 20px;
    box-shadow: 3px 3px 0 alpha({INK}, 0.12);
    padding: 16px;
}}

.ff-pill {{
    border-radius: 999px;
    border: 1px solid {INK};
    background-color: {CREAM};
    padding: 8px 16px;
}}

.ff-pill-active {{
    border-radius: 999px;
    border: 1px solid {INK};
    background-color: {LAVENDER};
    padding: 8px 16px;
    font-weight: 600;
}}

list.ff-sidebar {{
    background-color: {CREAM};
}}

list.ff-sidebar row {{
    border-radius: 999px;
    margin: 2px 8px;
    padding: 6px 10px;
}}

list.ff-sidebar row:selected {{
    background-color: {LAVENDER};
    color: {INK};
}}
"""


def apply_style() -> None:
    """Load CSS onto the default Gdk.Display at APPLICATION priority."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, Gtk

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode("utf-8"))
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
