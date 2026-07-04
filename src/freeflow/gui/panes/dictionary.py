"""Dictionary settings pane: list of forced-spelling entries + add/remove.

Plain word entries render as one pill ("Hyprland"); corrections render as
"wrong → Right". `entries_for_display` is the testable core; `build` wires it
into GTK widgets per the pinned GUI contract (docs/GUI.md).
"""
from __future__ import annotations

from freeflow.dictionary import Dictionary


def entries_for_display(dictionary: Dictionary) -> list[tuple[str, str]]:
    """Return (label, remove_key) pairs in file order.

    label is the plain word, or "wrong → Right" for corrections.
    remove_key is what Dictionary.remove() expects (the "wrong" side, or the
    plain word itself).
    """
    out: list[tuple[str, str]] = []
    for wrong, right in dictionary._pairs.items():
        if wrong == right.lower():
            out.append((right, right))
        else:
            out.append((f"{wrong} → {right}", wrong))
    return out


def build(ctx) -> "Gtk.Widget":  # noqa: F821 - Gtk imported lazily below
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    root.set_margin_top(16)
    root.set_margin_bottom(16)
    root.set_margin_start(16)
    root.set_margin_end(16)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.add_css_class("ff-card")
    root.append(card)

    title = Gtk.Label(label="Your Dictionary", xalign=0)
    title.add_css_class("ff-serif")
    card.append(title)

    rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    card.append(rows_box)

    def refresh() -> None:
        child = rows_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            rows_box.remove(child)
            child = nxt
        for label, remove_key in entries_for_display(ctx.dictionary):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            pill = Gtk.Label(label=label)
            pill.add_css_class("ff-pill")
            pill.set_hexpand(True)
            pill.set_xalign(0)
            row.append(pill)

            remove_btn = Gtk.Button(label="✕")
            remove_btn.add_css_class("ff-danger")

            def on_remove(_btn, key=remove_key) -> None:
                ctx.dictionary.remove(key)
                refresh()

            remove_btn.connect("clicked", on_remove)
            row.append(remove_btn)
            rows_box.append(row)

    add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    entry = Gtk.Entry()
    entry.set_placeholder_text("Add a word or correction…")
    entry.set_hexpand(True)
    add_row.append(entry)

    add_btn = Gtk.Button(label="Add")
    add_btn.add_css_class("ff-pill-active")

    def on_add(_btn=None) -> None:
        text = entry.get_text().strip()
        if not text:
            return
        ctx.dictionary.add(text)
        entry.set_text("")
        refresh()

    add_btn.connect("clicked", on_add)
    entry.connect("activate", on_add)
    add_row.append(add_btn)
    card.append(add_row)

    hint = Gtk.Label(label="Corrections you make get suggested here automatically.")
    hint.add_css_class("ff-muted")
    hint.set_xalign(0)
    card.append(hint)

    refresh()
    return root
