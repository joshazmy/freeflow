"""Tone & Apps pane: category defaults + per-app tone_overrides.

Tone-key decision (see report): context.tone_for() only ever looks up
cfg.tone_overrides by literal app_class (e.g. "discord"), it has no concept of
a "_email"/"_work_chat"/... category key. The 4 category rows are stored under
those underscore-prefixed keys anyway, per the contract's explicit fallback
instruction -- they currently do NOT affect tone_for's behavior, only the
built-in _EMAIL_APPS/_WORK_CHAT_APPS/_PERSONAL_CHAT_APPS sets in context.py do.
This is a real gap between the mockup's promise and the engine; flagged in the
final report, not fixed here (context.py is out of scope for agent B).
"""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

TONE_LEVELS = ["formal", "neutral", "casual"]

TONE_CATEGORIES = [
    ("Email", "_email"),
    ("Work chat", "_work_chat"),
    ("Personal chat", "_personal_chat"),
    ("Everything else", "_default"),
]

# Mirrors context.py's built-in fallback behavior, used only as the GUI's
# default displayed value when no override is stored yet.
_CATEGORY_DEFAULTS = {
    "_email": "formal",
    "_work_chat": "formal",
    "_personal_chat": "casual",
    "_default": "neutral",
}


def category_tone(cfg, key: str) -> str:
    return (cfg.tone_overrides or {}).get(key, _CATEGORY_DEFAULTS.get(key, "neutral"))


def per_app_overrides(cfg) -> dict:
    """Real per-app entries only -- excludes the reserved "_"-prefixed category keys."""
    return {k: v for k, v in (cfg.tone_overrides or {}).items() if not k.startswith("_")}


def _pill_segment(root_box, key, current, on_pick, name_prefix="tone"):
    seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    buttons = []

    def refresh(active_level):
        for b, level in buttons:
            if level == active_level:
                b.add_css_class("ff-pill-active")
            else:
                b.remove_css_class("ff-pill-active")

    for level in TONE_LEVELS:
        btn = Gtk.Button(label=level.capitalize())
        btn.add_css_class("ff-pill")
        btn.set_name(f"{name_prefix}-{key}-{level}")
        if level == current:
            btn.add_css_class("ff-pill-active")

        def on_clicked(_btn, level=level):
            on_pick(key, level)
            refresh(level)

        btn.connect("clicked", on_clicked)
        seg.append(btn)
        buttons.append((btn, level))
    root_box.append(seg)
    return seg


def _row(label_text: str, control: Gtk.Widget) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    lbl = Gtk.Label(label=label_text, xalign=0)
    lbl.set_hexpand(True)
    row.append(lbl)
    row.append(control)
    return row


def build(ctx) -> Gtk.Widget:
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    root.add_css_class("ff-card")

    def save_tone(key: str, level: str) -> None:
        overrides = dict(ctx.cfg.tone_overrides or {})
        overrides[key] = level
        ctx.save(tone_overrides=overrides)

    for label, key in TONE_CATEGORIES:
        seg_box = Gtk.Box()
        _pill_segment(seg_box, key, category_tone(ctx.cfg, key), save_tone)
        root.append(_row(label, seg_box))

    heading = Gtk.Label(label="Per-app overrides", xalign=0)
    heading.add_css_class("ff-serif")
    root.append(heading)

    apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    apps_box.set_name("tone-apps-box")
    root.append(apps_box)

    def rebuild_apps():
        child = apps_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            apps_box.remove(child)
            child = nxt
        for app, level in per_app_overrides(ctx.cfg).items():
            seg_box = Gtk.Box()
            _pill_segment(seg_box, app, level, save_tone)
            apps_box.append(_row(app, seg_box))

    rebuild_apps()

    add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    entry = Gtk.Entry()
    entry.set_placeholder_text("app name…")
    entry.set_name("tone-add-app-entry")
    add_btn = Gtk.Button(label="+ Add app")
    add_btn.add_css_class("ff-pill")
    add_btn.set_name("tone-add-app-button")

    def on_add(_btn):
        app = entry.get_text().strip().lower()
        if not app:
            return
        save_tone(app, "neutral")
        entry.set_text("")
        rebuild_apps()

    add_btn.connect("clicked", on_add)
    add_row.append(entry)
    add_row.append(add_btn)
    root.append(add_row)

    return root
