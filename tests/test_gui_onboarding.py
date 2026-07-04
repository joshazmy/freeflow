"""Onboarding wizard: plain probes tested headless, widget flow tested via GTK."""
import os

import pytest

from freeflow.config import load, save_default
from freeflow.gui import onboarding
from freeflow.gui.state import GuiContext


def _ctx(tmp_path):
    cfg_path = tmp_path / "config.toml"
    save_default(str(cfg_path))
    cfg = load(str(cfg_path))
    cfg.dictionary_path = str(tmp_path / "dictionary.txt")
    return GuiContext(cfg=cfg, config_path=str(cfg_path))


# ---------- plain-function probes (headless) ----------

def test_user_in_input_group_true(monkeypatch):
    class FakeGroup:
        gr_gid = 42

    monkeypatch.setattr(onboarding.grp, "getgrnam", lambda name: FakeGroup())
    monkeypatch.setattr(onboarding.os, "getgroups", lambda: [1, 42, 100])
    assert onboarding.user_in_input_group() is True


def test_user_in_input_group_false_when_not_member(monkeypatch):
    class FakeGroup:
        gr_gid = 42

    monkeypatch.setattr(onboarding.grp, "getgrnam", lambda name: FakeGroup())
    monkeypatch.setattr(onboarding.os, "getgroups", lambda: [1, 100])
    assert onboarding.user_in_input_group() is False


def test_user_in_input_group_false_when_group_missing(monkeypatch):
    def raise_keyerror(name):
        raise KeyError(name)

    monkeypatch.setattr(onboarding.grp, "getgrnam", raise_keyerror)
    assert onboarding.user_in_input_group() is False


def test_ydotool_socket_present_via_env(tmp_path, monkeypatch):
    sock = tmp_path / "ydotoold.socket"
    sock.touch()
    monkeypatch.setenv("YDOTOOL_SOCKET", str(sock))
    assert onboarding.ydotool_socket_present() is True


def test_ydotool_socket_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("YDOTOOL_SOCKET", str(tmp_path / "nope.socket"))
    assert onboarding.ydotool_socket_present() is False


def test_mic_test_passed_true(monkeypatch):
    def fake_record(path, duration=2):
        with open(path, "wb") as f:
            f.write(b"0" * 20000)

    monkeypatch.setattr(onboarding, "record_mic_sample", fake_record)
    assert onboarding.mic_test_passed() is True


def test_mic_test_passed_false_for_tiny_file(monkeypatch):
    def fake_record(path, duration=2):
        with open(path, "wb") as f:
            f.write(b"0" * 10)

    monkeypatch.setattr(onboarding, "record_mic_sample", fake_record)
    assert onboarding.mic_test_passed() is False


# ---------- widget flow (GTK) ----------

def test_onboarding_window_step_navigation(tmp_path):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    ctx = _ctx(tmp_path)
    win = onboarding.OnboardingWindow(application=None, ctx=ctx)

    assert win.stack.get_visible_child_name() == "permissions"
    win._on_next(None)
    assert win.stack.get_visible_child_name() == "mic"
    win._on_prev(None)
    assert win.stack.get_visible_child_name() == "permissions"


def test_onboarding_finish_writes_onboarded_marker(tmp_path, monkeypatch):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    marker = tmp_path / ".onboarded"
    monkeypatch.setattr(onboarding, "ONBOARDED_PATH", marker)

    ctx = _ctx(tmp_path)
    win = onboarding.OnboardingWindow(application=None, ctx=ctx)

    for name in onboarding.OnboardingWindow.STEP_NAMES[1:]:
        win.stack.set_visible_child_name(name)
        win._on_next(None)

    assert marker.exists()


def test_shortcut_step_saves_preset(tmp_path):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    ctx = _ctx(tmp_path)
    win = onboarding.OnboardingWindow(application=None, ctx=ctx)
    preset_keys = onboarding.SHORTCUT_PRESETS[1][1]
    win._shortcut_buttons[preset_keys].emit("clicked")
    assert ctx.cfg.keys == preset_keys
    assert load(ctx.config_path).keys == preset_keys


def test_language_step_saves_language(tmp_path):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    ctx = _ctx(tmp_path)
    win = onboarding.OnboardingWindow(application=None, ctx=ctx)
    code = onboarding.LANGUAGES[2][1]
    win._language_buttons[code].emit("clicked")
    assert ctx.cfg.language == code
    assert load(ctx.config_path).language == code


def test_tryit_step_runs_engine_and_shows_result(tmp_path, monkeypatch):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib

    if not Gtk.init_check():
        pytest.skip("no display available")

    class FakeEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def process(self, text):
            return ("can you send the file?", False)

    import freeflow.engine as real_engine
    monkeypatch.setattr(real_engine, "Engine", FakeEngine)

    ctx = _ctx(tmp_path)
    win = onboarding.OnboardingWindow(application=None, ctx=ctx)
    win._tryit_run_btn.emit("clicked")

    # engine runs in a background thread; pump the main loop until it reports back
    for _ in range(200):
        while GLib.MainContext.default().iteration(False):
            pass
        if win._tryit_result.get_label():
            break
        import time
        time.sleep(0.01)

    assert win._tryit_result.get_label() == "can you send the file?"
