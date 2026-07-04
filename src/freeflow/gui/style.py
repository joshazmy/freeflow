"""Freeflow GTK4 stylesheet — Wispr Flow visual language (design/mockup.html).

Shared CSS classes other pane modules should use:
  .ff-card          card: 1px border, radius 20px, hard shadow
  .ff-pill          pill button/row: radius 999px, 1px border, bg
  .ff-pill-active   active/selected pill or sidebar row: lavender bg + ink border/text
  .ff-serif         display serif heading (Sentient/P052/Georgia)
  .ff-wordmark      italic bold serif wordmark ("Freeflow" sidebar label)
  .ff-muted         secondary/caption text (dimmed)
  .ff-danger        destructive text/button accents (quit, remove, offline)
  .ff-mono          monospace chip (e.g. `$ freeflow status`)

Window/app chrome uses plain widget selectors (window, list, listboxrow, switch) so
this file is the single source of truth for color tokens; pane modules only need the
class names above.

Light and dark share one shape/typography language; only the color tokens swap.
`build_css(dark)` is a pure function — no GTK import, headless-testable. `apply_style`
is the only GTK-touching entry point, and it is re-callable at runtime (live theme
switch): it keeps the last provider in a module global and removes it from the
display before adding the new one, so themes never stack.
"""
from __future__ import annotations

CREAM = "#FFFEF0"
INK = "#111110"
LAVENDER = "#E7D4F9"

# dark tokens (docs/GUI-round3.md "Palette (agent A)")
DARK_BG = "#171613"
DARK_CARD = "#211F1B"
DARK_DANGER = "#E08080"
LIGHT_DANGER = "#a33333"


def build_css(dark: bool) -> str:
    """Return the full GTK4 CSS for the light (dark=False) or dark (dark=True) theme."""
    if dark:
        bg = DARK_BG
        card_bg = DARK_CARD
        text = CREAM
        border = f"alpha({CREAM}, 0.25)"
        shadow = f"3px 3px 0 alpha({CREAM}, 0.12)"
        muted_color = CREAM
        danger = DARK_DANGER
        switch_unchecked_bg = DARK_CARD
        switch_border = f"alpha({CREAM}, 0.35)"
        switch_knob = CREAM
    else:
        bg = CREAM
        card_bg = "#FFFFFF"
        text = INK
        border = INK
        shadow = f"3px 3px 0 alpha({INK}, 0.12)"
        muted_color = INK
        danger = LIGHT_DANGER
        switch_unchecked_bg = CREAM
        switch_border = INK
        switch_knob = INK

    return f"""
window {{
    background-color: {bg};
    color: {text};
    font-family: "General Sans", "Inter", "Cantarell", sans-serif;
}}

.ff-serif {{
    font-family: "Sentient", "P052", "Georgia", serif;
}}

.ff-wordmark {{
    font-family: "Noto Serif", serif;
    font-style: italic;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

.ff-muted {{
    color: {muted_color};
    opacity: 0.6;
    font-size: 90%;
}}

.ff-danger {{
    color: {danger};
}}

.ff-mono {{
    font-family: monospace;
    background-color: {LAVENDER};
    color: {INK};
    border: 1px solid {INK};
    border-radius: 999px;
    padding: 6px 14px;
}}

.ff-card {{
    background-color: {card_bg};
    color: {text};
    border: 1px solid {border};
    border-radius: 20px;
    box-shadow: {shadow};
    padding: 16px;
}}

.ff-pill {{
    border-radius: 999px;
    border: 1px solid {border};
    background-color: {card_bg};
    color: {text};
    padding: 8px 16px;
}}

.ff-pill-active {{
    border-radius: 999px;
    border: 1px solid {INK};
    background-color: {LAVENDER};
    color: {INK};
    padding: 8px 16px;
    font-weight: 600;
}}

list.ff-sidebar {{
    background-color: {bg};
}}

list.ff-sidebar row {{
    border-radius: 999px;
    margin: 2px 8px;
    padding: 6px 10px;
    color: {text};
}}

list.ff-sidebar row:selected {{
    background-color: {LAVENDER};
    color: {INK};
}}

switch {{
    border-radius: 999px;
    border: 1px solid {switch_border};
    background-color: {switch_unchecked_bg};
    background-image: none;
    box-shadow: none;
}}

switch:checked {{
    background-color: {LAVENDER};
    background-image: none;
}}

switch slider {{
    border-radius: 999px;
    background-color: {switch_knob};
    background-image: none;
    box-shadow: none;
}}
"""


# Backward-compatible module-level constant: the light theme, as before this refactor.
CSS = build_css(False)

_current_provider = None


def apply_style(dark: bool = False) -> None:
    """Load CSS onto the default Gdk.Display at APPLICATION priority.

    Re-callable: swaps out any previously-applied provider instead of stacking
    another one on top, so live theme switching doesn't accumulate providers.
    """
    global _current_provider
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, Gtk

    provider = Gtk.CssProvider()
    provider.load_from_data(build_css(dark).encode("utf-8"))
    display = Gdk.Display.get_default()
    if display is not None:
        if _current_provider is not None:
            Gtk.StyleContext.remove_provider_for_display(display, _current_provider)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    _current_provider = provider
