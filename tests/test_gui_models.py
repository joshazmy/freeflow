"""Tests for gui/panes/models.py."""
import time

import pytest

from freeflow.config import load, save_default
from freeflow.gui.state import GuiContext
from freeflow.gui.panes import models


def _ctx(tmp_path, model_path=""):
    cfg_path = tmp_path / "config.toml"
    save_default(str(cfg_path))
    cfg = load(str(cfg_path))
    cfg.model_path = model_path
    return GuiContext(cfg=cfg, config_path=str(cfg_path))


# ---- headless logic ----

def test_model_name_from_path_plain():
    assert models.model_name_from_path("/models/ggml-base.bin") == "base"


def test_model_name_from_path_prefers_longest_match():
    assert models.model_name_from_path("/models/ggml-large-v3-turbo.bin") == "large-v3-turbo"
    assert models.model_name_from_path("/models/ggml-large-v3.bin") == "large-v3"


def test_model_name_from_path_empty():
    assert models.model_name_from_path("") == ""


def test_model_path_for_finds_sibling(tmp_path):
    (tmp_path / "ggml-base.bin").write_text("x")
    (tmp_path / "ggml-small.bin").write_text("x")
    current = str(tmp_path / "ggml-base.bin")
    found = models.model_path_for("small", current)
    assert found == str(tmp_path / "ggml-small.bin")


def test_model_path_for_missing_returns_none(tmp_path):
    current = str(tmp_path / "ggml-base.bin")
    (tmp_path / "ggml-base.bin").write_text("x")
    assert models.model_path_for("large-v3", current) is None


def test_ollama_connected_true(monkeypatch):
    class FakeResp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(models.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    assert models.ollama_connected("http://127.0.0.1:11434") is True


def test_ollama_connected_false_on_error(monkeypatch):
    def raise_err(*a, **k):
        raise OSError("refused")
    monkeypatch.setattr(models.urllib.request, "urlopen", raise_err)
    assert models.ollama_connected("http://127.0.0.1:11434") is False


# ---- widget tests ----

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

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


def _pump(seconds=1.0):
    ctx_glib = GLib.MainContext.default()
    end = time.time() + seconds
    while time.time() < end:
        while ctx_glib.iteration(False):
            pass
        time.sleep(0.01)


def test_build_returns_widget(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path, model_path="/models/ggml-base.bin")
    root = models.build(ctx)
    assert isinstance(root, Gtk.Widget)


def test_current_model_pill_active(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path, model_path="/models/ggml-base.bin")
    root = models.build(ctx)
    btn = _find(root, "model-pill-base")
    assert "ff-pill-active" in list(btn.get_css_classes())


def test_pick_unavailable_model_shows_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path, model_path=str(tmp_path / "ggml-base.bin"))
    (tmp_path / "ggml-base.bin").write_text("x")
    root = models.build(ctx)
    btn = _find(root, "model-pill-large-v3")
    btn.emit("clicked")
    hint = _find(root, "model-hint")
    assert "install.sh" in hint.get_label()
    assert ctx.cfg.model_path == str(tmp_path / "ggml-base.bin")  # unchanged, no save happened


def test_pick_available_model_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    (tmp_path / "ggml-base.bin").write_text("x")
    (tmp_path / "ggml-small.bin").write_text("x")
    ctx = _ctx(tmp_path, model_path=str(tmp_path / "ggml-base.bin"))
    root = models.build(ctx)
    btn = _find(root, "model-pill-small")
    btn.emit("clicked")
    assert load(ctx.config_path).model_path == str(tmp_path / "ggml-small.bin")


def test_cleanup_switch_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    sw = _find(root, "switch-cleanup")
    sw.set_active(not sw.get_active())
    assert load(ctx.config_path).cleanup == sw.get_active()


def test_ollama_model_entry_does_not_save_on_every_keystroke(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    entry = _find(root, "entry-ollama-model")
    entry.set_text("llama3:8b")
    # "changed" alone (no activate, no focus-out) must not persist.
    assert load(ctx.config_path).ollama_model != "llama3:8b"


def test_ollama_model_entry_persists_on_activate(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    entry = _find(root, "entry-ollama-model")
    entry.set_text("llama3:8b")
    entry.emit("activate")
    assert load(ctx.config_path).ollama_model == "llama3:8b"


def test_ollama_model_entry_persists_on_focus_leave(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    entry = _find(root, "entry-ollama-model")
    entry.set_text("mistral:7b")
    controllers = entry.observe_controllers()
    focus_controller = next(
        c for c in controllers if isinstance(c, Gtk.EventControllerFocus)
    )
    focus_controller.emit("leave")
    assert load(ctx.config_path).ollama_model == "mistral:7b"


def test_ollama_model_entry_no_duplicate_save_if_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    entry = _find(root, "entry-ollama-model")
    original = entry.get_text()
    saves = []
    real_save = ctx.save
    monkeypatch.setattr(ctx, "save", lambda **kw: (saves.append(kw), real_save(**kw))[1])
    entry.emit("activate")  # no change made
    assert saves == []


def test_badge_updates_from_probe_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    badge = _find(root, "ollama-badge")
    _pump(1.0)
    assert badge.get_label() == "connected"
