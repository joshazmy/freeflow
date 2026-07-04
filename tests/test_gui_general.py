"""Tests for gui/panes/general.py. Logic functions run headless; widget tests need a
real GTK display (skipped otherwise)."""
import subprocess

import pytest

from freeflow.config import load, save_default
from freeflow.gui.state import GuiContext
from freeflow.gui.panes import general


def _ctx(tmp_path):
    cfg_path = tmp_path / "config.toml"
    save_default(str(cfg_path))
    cfg = load(str(cfg_path))
    return GuiContext(cfg=cfg, config_path=str(cfg_path))


# ---- headless logic ----

def test_pretty_chord_default():
    assert general.pretty_chord("KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT") == \
        "⌃ Ctrl + ⌥ Alt + ⇧ Shift (hold)"


def test_pretty_chord_two_keys():
    assert general.pretty_chord("KEY_LEFTCTRL,KEY_LEFTMETA") == "⌃ Ctrl + ⌘ Super (hold)"


def test_pretty_chord_unknown_key_passthrough():
    assert general.pretty_chord("KEY_WEIRD") == "KEY_WEIRD (hold)"


def test_chord_presets_shape():
    assert 3 <= len(general.CHORD_PRESETS) <= 4
    labels = [p[0] for p in general.CHORD_PRESETS]
    keys = [p[1] for p in general.CHORD_PRESETS]
    assert "KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT" in keys
    assert len(set(labels)) == len(labels)


def test_is_login_enabled_true(monkeypatch):
    def fake_run(*a, **k):
        return subprocess.CompletedProcess(a, 0, stdout="enabled\n", stderr="")
    monkeypatch.setattr(general.subprocess, "run", fake_run)
    assert general.is_login_enabled() is True


def test_is_login_enabled_false_on_missing_systemctl(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(general.subprocess, "run", fake_run)
    assert general.is_login_enabled() is False


def test_set_login_enabled_calls_systemctl(monkeypatch):
    calls = []
    def fake_run(cmd, **k):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(general.subprocess, "run", fake_run)
    general.set_login_enabled(True)
    general.set_login_enabled(False)
    assert calls == [
        ["systemctl", "--user", "enable", "freeflow"],
        ["systemctl", "--user", "disable", "freeflow"],
    ]


def test_set_login_enabled_never_raises(monkeypatch):
    def fake_run(*a, **k):
        raise OSError("no systemd")
    monkeypatch.setattr(general.subprocess, "run", fake_run)
    general.set_login_enabled(True)  # must not raise


# ---- widget tests (real GTK) ----

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check():
    pytest.skip("no display available for GTK widget tests", allow_module_level=True)


def _find(widget, name):
    if widget.get_name() == name:
        return widget
    child = widget.get_first_child()
    while child is not None:
        found = _find(child, name)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


def test_build_returns_widget(tmp_path):
    ctx = _ctx(tmp_path)
    root = general.build(ctx)
    assert isinstance(root, Gtk.Widget)


def test_switches_reflect_cfg(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.cfg.hands_free = True
    ctx.cfg.paste = False
    root = general.build(ctx)
    assert _find(root, "switch-hands-free").get_active() is True
    assert _find(root, "switch-paste").get_active() is False


def test_toggle_hands_free_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(general, "is_login_enabled", lambda: False)
    ctx = _ctx(tmp_path)
    root = general.build(ctx)
    sw = _find(root, "switch-hands-free")
    sw.set_active(not sw.get_active())
    assert load(ctx.config_path).hands_free == sw.get_active()


def test_hotkey_preset_click_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(general, "is_login_enabled", lambda: False)
    ctx = _ctx(tmp_path)
    root = general.build(ctx)
    preset_label, preset_keys = general.CHORD_PRESETS[1]
    btn = _find(root, f"hotkey-preset-{preset_keys}")
    assert btn is not None
    btn.emit("clicked")
    assert load(ctx.config_path).keys == preset_keys


def test_language_pill_click_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(general, "is_login_enabled", lambda: False)
    ctx = _ctx(tmp_path)
    root = general.build(ctx)
    pill = _find(root, "lang-pill-auto")
    assert pill is not None
    pill.emit("clicked")
    assert load(ctx.config_path).language == "auto"


def test_start_login_switch_calls_setter(tmp_path, monkeypatch):
    monkeypatch.setattr(general, "is_login_enabled", lambda: False)
    calls = []
    monkeypatch.setattr(general, "set_login_enabled", lambda v: calls.append(v))
    ctx = _ctx(tmp_path)
    root = general.build(ctx)
    sw = _find(root, "switch-start-login")
    assert sw.get_active() is False
    sw.set_active(True)
    assert calls == [True]
