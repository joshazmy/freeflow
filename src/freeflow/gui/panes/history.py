"""History pane: recent dictations, newest first. `format_caption` /
`display_entries` are the testable core; `build` wires them into GTK widgets
per the pinned GUI contract (docs/GUI.md).
"""
from __future__ import annotations

import time

from freeflow.history import History

# Module-level factory so tests can monkeypatch which History (and thus which
# on-disk file) the pane reads from.
HISTORY_FACTORY = History

MAX_LABEL_LEN = 80


def format_caption(entry: dict) -> str:
    hhmm = time.strftime("%H:%M", time.localtime(entry["ts"]))
    return f"{entry['app']} · {entry['tone']} · {hhmm}"


def display_entries(history, limit: int = 50) -> list[dict]:
    """Newest-first entries from `history.read_all()`, capped at `limit`."""
    return history.read_all()[:limit]


def _ellipsize(text: str, max_len: int = MAX_LABEL_LEN) -> str:
    text = text.replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def build(ctx) -> "Gtk.Widget":  # noqa: F821 - Gtk imported lazily below
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, GLib, Gtk

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    root.set_margin_top(16)
    root.set_margin_bottom(16)
    root.set_margin_start(16)
    root.set_margin_end(16)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.add_css_class("ff-card")
    root.append(card)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    title = Gtk.Label(label="History", xalign=0)
    title.add_css_class("ff-serif")
    title.set_hexpand(True)
    header.append(title)

    refresh_btn = Gtk.Button(label="Refresh")
    refresh_btn.add_css_class("ff-pill")
    header.append(refresh_btn)
    card.append(header)

    scroller = Gtk.ScrolledWindow()
    scroller.set_min_content_height(320)
    scroller.set_vexpand(True)
    card.append(scroller)

    rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    scroller.set_child(rows_box)

    footer = Gtk.Label(
        label="Kept locally, last 200 dictations. Clear it in Data & Privacy.",
        xalign=0,
    )
    footer.add_css_class("ff-muted")
    card.append(footer)

    def copy_to_clipboard(text: str, caption_label) -> None:
        display = Gdk.Display.get_default()
        clipboard = display.get_clipboard()
        clipboard.set(text)
        original = caption_label.get_label()
        caption_label.set_label("copied ✓")

        def restore() -> bool:
            caption_label.set_label(original)
            return False

        GLib.timeout_add(1500, restore)

    def refresh() -> None:
        child = rows_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            rows_box.remove(child)
            child = nxt

        history = HISTORY_FACTORY()
        entries = display_entries(history)

        if not entries:
            empty = Gtk.Label(
                label="No dictations yet — hold the hotkey and speak.",
                xalign=0,
            )
            empty.add_css_class("ff-muted")
            rows_box.append(empty)
            return

        for entry in entries:
            pill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            pill.add_css_class("ff-pill")

            text_label = Gtk.Label(label=_ellipsize(entry["cleaned"]), xalign=0)
            pill.append(text_label)

            caption = Gtk.Label(label=format_caption(entry), xalign=0)
            caption.add_css_class("ff-muted")
            pill.append(caption)

            click = Gtk.GestureClick()

            def on_click(_gesture, _n_press, _x, _y, cleaned=entry["cleaned"], cap=caption):
                copy_to_clipboard(cleaned, cap)

            click.connect("released", on_click)
            pill.add_controller(click)

            expander = Gtk.Expander(label="⌄")
            raw_label = Gtk.Label(label=entry["raw"], xalign=0)
            raw_label.add_css_class("ff-mono")
            raw_label.set_wrap(True)
            expander.set_child(raw_label)
            pill.append(expander)

            rows_box.append(pill)

    refresh_btn.connect("clicked", lambda _btn: refresh())

    refresh()
    root._ff_refresh_button = refresh_btn
    return root
