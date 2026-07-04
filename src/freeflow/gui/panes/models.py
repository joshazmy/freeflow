"""Models pane: speech-to-text model picker + cleanup/Ollama card."""
from __future__ import annotations

import threading
import urllib.request
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

MODEL_ALTERNATIVES = ["base", "small", "large-v3", "large-v3-turbo"]


def model_name_from_path(path: str) -> str:
    if not path:
        return ""
    stem = Path(path).stem
    for name in sorted(MODEL_ALTERNATIVES, key=len, reverse=True):
        if name in stem:
            return name
    return stem


def model_path_for(name: str, current_path: str) -> str | None:
    """Sibling ggml file matching `name` in the same directory as current_path, if any."""
    if not current_path:
        return None
    directory = Path(current_path).parent
    if not directory.is_dir():
        return None
    for f in sorted(directory.glob(f"*{name}*.bin")):
        return str(f)
    return None


def ollama_connected(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _row(control_left: Gtk.Widget, control_right: Gtk.Widget | None = None) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    control_left.set_hexpand(True)
    row.append(control_left)
    if control_right is not None:
        row.append(control_right)
    return row


def _card(title: str) -> Gtk.Box:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.add_css_class("ff-card")
    heading = Gtk.Label(label=title, xalign=0)
    heading.add_css_class("ff-serif")
    card.append(heading)
    return card


def build(ctx) -> Gtk.Widget:
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

    # --- Speech-to-text card ---
    stt_card = _card("Speech-to-text")

    current_name = model_name_from_path(ctx.cfg.model_path)
    current_label = Gtk.Label(label=f"Model: {current_name or '(none)'}", xalign=0)
    stt_card.append(current_label)

    hint_label = Gtk.Label(label="", xalign=0)
    hint_label.set_name("model-hint")
    hint_label.add_css_class("ff-muted")

    pill_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    pills = []

    def refresh_pills(active_name):
        for b, name in pills:
            if name == active_name:
                b.add_css_class("ff-pill-active")
            else:
                b.remove_css_class("ff-pill-active")

    for name in MODEL_ALTERNATIVES:
        btn = Gtk.Button(label=name)
        btn.add_css_class("ff-pill")
        btn.set_name(f"model-pill-{name}")
        if name == current_name:
            btn.add_css_class("ff-pill-active")

        def on_pick(_btn, name=name):
            if name == model_name_from_path(ctx.cfg.model_path):
                return
            found = model_path_for(name, ctx.cfg.model_path)
            if found:
                ctx.save(model_path=found)
                current_label.set_label(f"Model: {name}")
                hint_label.set_label("")
                refresh_pills(name)
            else:
                hint_label.set_label("run install.sh to download models")

        btn.connect("clicked", on_pick)
        pill_row.append(btn)
        pills.append((btn, name))

    stt_card.append(pill_row)
    badge = Gtk.Label(label="auto-picked for your GPU")
    badge.add_css_class("ff-muted")
    stt_card.append(badge)
    stt_card.append(hint_label)
    root.append(stt_card)

    # --- Cleanup card ---
    cleanup_card = _card("Cleanup")

    cleanup_sw = Gtk.Switch(active=ctx.cfg.cleanup)
    cleanup_sw.set_name("switch-cleanup")
    cleanup_sw.connect("notify::active", lambda sw, _p: ctx.save(cleanup=sw.get_active()))

    ollama_badge = Gtk.Label(label="…")
    ollama_badge.set_name("ollama-badge")
    ollama_badge.add_css_class("ff-muted")

    status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    status_row.append(ollama_badge)
    cleanup_card.append(_row(status_row, cleanup_sw))

    entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    model_label = Gtk.Label(label="Ollama model:")
    entry = Gtk.Entry()
    entry.set_text(ctx.cfg.ollama_model)
    entry.set_name("entry-ollama-model")

    def save_if_changed(*_a):
        text = entry.get_text()
        if text != ctx.cfg.ollama_model:
            ctx.save(ollama_model=text)

    entry.connect("activate", save_if_changed)
    focus_controller = Gtk.EventControllerFocus()
    focus_controller.connect("leave", save_if_changed)
    entry.add_controller(focus_controller)
    entry_row.append(model_label)
    entry_row.append(entry)
    cleanup_card.append(entry_row)

    desc = Gtk.Label(label='"AI cleanup" toggle above — off = raw dictation still works.', xalign=0)
    desc.add_css_class("ff-muted")
    cleanup_card.append(desc)

    root.append(cleanup_card)

    def _set_badge(connected):
        ollama_badge.set_label("connected" if connected else "offline")
        return False

    def _probe():
        connected = ollama_connected(ctx.cfg.ollama_url)
        GLib.idle_add(_set_badge, connected)

    threading.Thread(target=_probe, daemon=True).start()

    return root
