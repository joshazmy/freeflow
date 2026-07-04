"""Freeflow status-notifier tray icon via AppIndicator3 (GTK3, own process --
never share a process with the GTK4 settings window). Imports cleanly without
the typelib; main() fails soft with an install hint."""
from __future__ import annotations

import subprocess
import sys

from freeflow.config import load, save_values

UNIT = "freeflow"
TONE_CHOICES = (("Neutral", "neutral"), ("Formal", "formal"), ("Casual", "casual"))


def open_settings() -> None:
    try:
        subprocess.Popen([sys.executable, "-m", "freeflow.cli", "gui"])
    except Exception:
        pass


def dictation_active() -> bool:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", UNIT],
                            capture_output=True, text=True, timeout=2)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def toggle_dictation() -> None:
    action = "stop" if dictation_active() else "start"
    try:
        subprocess.run(["systemctl", "--user", action, UNIT], timeout=2)
    except Exception:
        pass


def toggle_label(active: bool) -> str:
    return "Pause dictation" if active else "Resume dictation"


def current_default_tone(path: str | None = None) -> str:
    return load(path).tone_overrides.get("_default", "neutral")


def set_default_tone(value: str, path: str | None = None) -> None:
    merged = dict(load(path).tone_overrides)
    merged["_default"] = value
    save_values({"tone_overrides": merged}, path)


def _load_appindicator():
    """Return (Gtk3, AppIndicator3) or None if the typelib isn't available."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3, Gtk
        except (ImportError, ValueError):
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator3
            from gi.repository import Gtk
        return Gtk, AppIndicator3
    except (ImportError, ValueError):
        return None


def _build_indicator(Gtk, AppIndicator3):
    """Build the indicator + menu; returns (indicator, menu_labels)."""
    ind = AppIndicator3.Indicator.new(
        "freeflow", "audio-input-microphone",
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
    ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    ind.set_title("Freeflow")

    menu = Gtk.Menu()

    mi_settings = Gtk.MenuItem(label="Open Settings")
    mi_settings.connect("activate", lambda *_: open_settings())

    mi_toggle = Gtk.MenuItem(label=toggle_label(dictation_active()))

    def _on_toggle(*_):
        toggle_dictation()
        mi_toggle.set_label(toggle_label(dictation_active()))
    mi_toggle.connect("activate", _on_toggle)

    mi_tone = Gtk.MenuItem(label="Default tone")
    tone_menu = Gtk.Menu()
    active_tone = current_default_tone()
    group = None
    for label, value in TONE_CHOICES:
        item = Gtk.RadioMenuItem(label=label, group=group)
        group = item
        if value == active_tone:
            item.set_active(True)

        def _on_tone_toggled(widget, value=value):
            if widget.get_active():
                set_default_tone(value)
        item.connect("toggled", _on_tone_toggled)
        tone_menu.append(item)
    mi_tone.set_submenu(tone_menu)

    mi_quit = Gtk.MenuItem(label="Quit tray")
    mi_quit.connect("activate", lambda *_: Gtk.main_quit())

    for item in (mi_settings, mi_toggle, mi_tone, Gtk.SeparatorMenuItem(), mi_quit):
        menu.append(item)
    menu.show_all()
    ind.set_menu(menu)

    labels = [mi_settings.get_label(), mi_toggle.get_label(), mi_tone.get_label(), mi_quit.get_label()]
    return ind, labels


def main() -> int:
    mods = _load_appindicator()
    if mods is None:
        print("tray needs the AppIndicator3 typelib: "
              "dnf install libappindicator-gtk3 "
              "(apt: gir1.2-ayatanaappindicator3-0.1, pacman: libappindicator-gtk3)")
        return 1
    Gtk, AppIndicator3 = mods
    _indicator, _ = _build_indicator(Gtk, AppIndicator3)
    Gtk.main()
    return 0
