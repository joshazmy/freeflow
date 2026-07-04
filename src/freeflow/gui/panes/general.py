"""General settings pane: hotkey, hands-free, paste, language, start at login."""
from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

# ---- plain logic (unit-testable headless) ----

_KEY_SYMBOLS = {
    "KEY_LEFTCTRL": "⌃ Ctrl", "KEY_RIGHTCTRL": "⌃ Ctrl",
    "KEY_LEFTALT": "⌥ Alt", "KEY_RIGHTALT": "⌥ Alt",
    "KEY_LEFTSHIFT": "⇧ Shift", "KEY_RIGHTSHIFT": "⇧ Shift",
    "KEY_LEFTMETA": "⌘ Super", "KEY_RIGHTMETA": "⌘ Super",
}

CHORD_PRESETS = [
    ("Ctrl + Alt + Shift", "KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT"),
    ("Ctrl + Super", "KEY_LEFTCTRL,KEY_LEFTMETA"),
    ("Alt + Super", "KEY_LEFTALT,KEY_LEFTMETA"),
    ("Ctrl + Shift", "KEY_LEFTCTRL,KEY_LEFTSHIFT"),
]

LANGUAGE_PILLS = [
    ("English (auto)", "en"),
    ("Auto (multilingual)", "auto"),
    ("Español", "es"),
    ("Français", "fr"),
    ("Deutsch", "de"),
]


def pretty_chord(keys_str: str) -> str:
    parts = [_KEY_SYMBOLS.get(k.strip(), k.strip()) for k in keys_str.split(",") if k.strip()]
    return " + ".join(parts) + " (hold)"


def is_login_enabled() -> bool:
    try:
        out = subprocess.run(
            ["systemctl", "--user", "is-enabled", "freeflow"],
            capture_output=True, text=True, timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.stdout.strip() == "enabled"


def set_login_enabled(enable: bool) -> None:
    try:
        subprocess.run(
            ["systemctl", "--user", "enable" if enable else "disable", "freeflow"],
            capture_output=True, timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        pass  # best-effort; no systemd is not fatal


# ---- widget ----

def _row(title: str, desc: str | None, control: Gtk.Widget) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.set_hexpand(True)
    labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    lbl = Gtk.Label(label=title, xalign=0)
    labels.append(lbl)
    if desc:
        d = Gtk.Label(label=desc, xalign=0)
        d.add_css_class("ff-muted")
        labels.append(d)
    labels.set_hexpand(True)
    row.append(labels)
    row.append(control)
    return row


def _pill_button(label: str, active: bool) -> Gtk.Button:
    btn = Gtk.Button(label=label)
    btn.add_css_class("ff-pill")
    if active:
        btn.add_css_class("ff-pill-active")
    return btn


def build(ctx) -> Gtk.Widget:
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    root.add_css_class("ff-card")

    # Hotkey row
    hotkey_label = Gtk.Label(label=pretty_chord(ctx.cfg.keys))
    hotkey_label.add_css_class("ff-muted")
    change_btn = Gtk.MenuButton(label="change")
    change_btn.add_css_class("ff-pill")
    popover = Gtk.Popover()
    preset_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    for preset_label, preset_keys in CHORD_PRESETS:
        pbtn = Gtk.Button(label=preset_label)
        pbtn.set_name(f"hotkey-preset-{preset_keys}")

        def on_preset_clicked(_btn, keys=preset_keys):
            ctx.save(keys=keys)
            hotkey_label.set_label(pretty_chord(keys))
            popover.popdown()

        pbtn.connect("clicked", on_preset_clicked)
        preset_box.append(pbtn)
    popover.set_child(preset_box)
    change_btn.set_popover(popover)
    hotkey_ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    hotkey_ctrl.append(hotkey_label)
    hotkey_ctrl.append(change_btn)
    root.append(_row("Hotkey", "Hold to dictate", hotkey_ctrl))

    # Hands-free switch
    hands_free_sw = Gtk.Switch(active=ctx.cfg.hands_free)
    hands_free_sw.set_name("switch-hands-free")
    hands_free_sw.connect(
        "notify::active", lambda sw, _p: ctx.save(hands_free=sw.get_active())
    )
    root.append(_row(
        "Hands-free", "Double-tap hotkey to toggle instead of holding", hands_free_sw
    ))

    # Paste result switch
    paste_sw = Gtk.Switch(active=ctx.cfg.paste)
    paste_sw.set_name("switch-paste")
    paste_sw.connect("notify::active", lambda sw, _p: ctx.save(paste=sw.get_active()))
    root.append(_row(
        "Paste result", "Off = type character-by-character instead", paste_sw
    ))

    # Language pill row
    lang_row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    lang_buttons = []

    def refresh_lang_pills(active_value):
        for b, value in lang_buttons:
            if value == active_value:
                b.add_css_class("ff-pill-active")
            else:
                b.remove_css_class("ff-pill-active")

    for label, value in LANGUAGE_PILLS:
        btn = _pill_button(label, value == ctx.cfg.language)
        btn.set_name(f"lang-pill-{value}")

        def on_lang_clicked(_btn, value=value):
            ctx.save(language=value)
            refresh_lang_pills(value)

        btn.connect("clicked", on_lang_clicked)
        lang_row_box.append(btn)
        lang_buttons.append((btn, value))
    root.append(_row("Language", "Auto-detect or pick from 100+ languages", lang_row_box))

    # Start at login switch
    login_sw = Gtk.Switch(active=is_login_enabled())
    login_sw.set_name("switch-start-login")
    login_sw.connect("notify::active", lambda sw, _p: set_login_enabled(sw.get_active()))
    root.append(_row("Start at login", None, login_sw))

    return root
