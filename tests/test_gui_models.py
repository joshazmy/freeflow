"""Tests for gui/panes/models.py."""
import json
import time
from pathlib import Path

import pytest

from freeflow.config import Config, load, save_default
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


# ---- new pure helpers ----

def test_model_url():
    assert models.model_url("large-v3") == (
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin"
    )


def test_download_dir_uses_model_parent():
    assert models.download_dir(Config(model_path="/a/b/ggml-base.bin")) == Path("/a/b")


def test_download_dir_default_when_unset():
    assert models.download_dir(Config(model_path="")) == Path(
        "~/.local/share/freeflow/models"
    ).expanduser()


def test_parse_pull_line_with_progress():
    assert models.parse_pull_line(
        '{"status":"downloading","completed":50,"total":100}'
    ) == ("downloading", 0.5)


def test_parse_pull_line_no_progress():
    assert models.parse_pull_line('{"status":"verifying sha256 digest"}') == (
        "verifying sha256 digest",
        None,
    )


def test_parse_pull_line_zero_total_is_pulse():
    assert models.parse_pull_line('{"status":"x","completed":0,"total":0}') == ("x", None)


def test_parse_pull_line_blank_and_junk():
    assert models.parse_pull_line("") == ("", None)
    assert models.parse_pull_line("not json") == ("", None)


def test_ollama_models_normalizes_latest(monkeypatch):
    payload = json.dumps(
        {"models": [{"name": "llama3:latest"}, {"name": "qwen3:1.7b"}]}
    ).encode()

    class R:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return payload

    monkeypatch.setattr(models.urllib.request, "urlopen", lambda *a, **k: R())
    assert models.ollama_models("http://127.0.0.1:11434") == ["llama3", "qwen3:1.7b"]


class _FakeResp:
    def __init__(self, chunks, headers):
        self._chunks = list(chunks)
        self.headers = headers
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n=-1):
        return self._chunks.pop(0) if self._chunks else b""


def test_download_model_writes_and_renames(tmp_path):
    fractions = []

    def fake_urlopen(url):
        return _FakeResp([b"hello", b"world"], {"Content-Length": "10"})

    path = models.download_model(
        "http://x/ggml-base.bin", tmp_path, "base",
        urlopen=fake_urlopen, progress=fractions.append,
    )
    assert path == tmp_path / "ggml-base.bin"
    assert path.read_bytes() == b"helloworld"
    assert not (tmp_path / "base.part").exists()
    assert fractions[-1] == 1.0


def test_download_model_pulses_without_content_length(tmp_path):
    fractions = []

    def fake_urlopen(url):
        return _FakeResp([b"data"], {})

    models.download_model(
        "http://x", tmp_path, "small", urlopen=fake_urlopen, progress=fractions.append
    )
    assert fractions == [None]


def test_download_model_cleans_up_on_failure(tmp_path):
    class Boom(_FakeResp):
        def read(self, n=-1):
            raise OSError("net down")

    def fake_urlopen(url):
        return Boom([], {})

    with pytest.raises(OSError):
        models.download_model("http://x", tmp_path, "base", urlopen=fake_urlopen)
    assert not (tmp_path / "base.part").exists()
    assert not (tmp_path / "ggml-base.bin").exists()


def test_cleanup_explanation_text():
    t = models.CLEANUP_EXPLANATION.lower()
    assert "filler" in t
    assert "raw" in t
    assert "never blocks" in t


# ---- widget tests ----

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

if not Gtk.init_check():
    pytest.skip("no display available for GTK widget tests", allow_module_level=True)


def _stub(monkeypatch, installed=("qwen3:1.7b",)):
    monkeypatch.setattr(models, "ollama_connected", lambda *a, **k: True)
    monkeypatch.setattr(models, "ollama_models", lambda *a, **k: list(installed))


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
    _stub(monkeypatch)
    ctx = _ctx(tmp_path, model_path="/models/ggml-base.bin")
    root = models.build(ctx)
    assert isinstance(root, Gtk.Widget)


def test_current_model_pill_active(tmp_path, monkeypatch):
    _stub(monkeypatch)
    ctx = _ctx(tmp_path, model_path="/models/ggml-base.bin")
    root = models.build(ctx)
    btn = _find(root, "model-pill-base")
    assert "ff-pill-active" in list(btn.get_css_classes())


def test_pick_unavailable_model_shows_download_pill(tmp_path, monkeypatch):
    _stub(monkeypatch)
    ctx = _ctx(tmp_path, model_path=str(tmp_path / "ggml-base.bin"))
    (tmp_path / "ggml-base.bin").write_text("x")
    root = models.build(ctx)
    _find(root, "model-pill-large-v3").emit("clicked")
    assert _find(root, "model-download-row").get_visible()
    assert "large-v3" in _find(root, "model-download").get_label()
    assert ctx.cfg.model_path == str(tmp_path / "ggml-base.bin")  # unchanged, no save yet


def test_download_click_saves_on_success(tmp_path, monkeypatch):
    _stub(monkeypatch)
    ctx = _ctx(tmp_path, model_path=str(tmp_path / "ggml-base.bin"))
    (tmp_path / "ggml-base.bin").write_text("x")

    def fake_download(url, ddir, name, **kw):
        p = Path(ddir) / f"ggml-{name}.bin"
        p.write_text("y")
        cb = kw.get("progress")
        if cb:
            cb(0.5)
            cb(1.0)
        return p

    monkeypatch.setattr(models, "download_model", fake_download)
    root = models.build(ctx)
    _find(root, "model-pill-large-v3").emit("clicked")
    _find(root, "model-download").emit("clicked")
    _pump(1.0)
    assert load(ctx.config_path).model_path == str(tmp_path / "ggml-large-v3.bin")
    # download row hidden again after success
    assert not _find(root, "model-download-row").get_visible()


def test_download_failure_shows_error(tmp_path, monkeypatch):
    _stub(monkeypatch)
    ctx = _ctx(tmp_path, model_path=str(tmp_path / "ggml-base.bin"))
    (tmp_path / "ggml-base.bin").write_text("x")

    def boom(url, ddir, name, **kw):
        raise OSError("connection reset")

    monkeypatch.setattr(models, "download_model", boom)
    root = models.build(ctx)
    _find(root, "model-pill-large-v3").emit("clicked")
    _find(root, "model-download").emit("clicked")
    _pump(1.0)
    assert "connection reset" in _find(root, "model-hint").get_label()
    assert ctx.cfg.model_path == str(tmp_path / "ggml-base.bin")


def test_pick_available_model_saves(tmp_path, monkeypatch):
    _stub(monkeypatch)
    (tmp_path / "ggml-base.bin").write_text("x")
    (tmp_path / "ggml-small.bin").write_text("x")
    ctx = _ctx(tmp_path, model_path=str(tmp_path / "ggml-base.bin"))
    root = models.build(ctx)
    _find(root, "model-pill-small").emit("clicked")
    assert load(ctx.config_path).model_path == str(tmp_path / "ggml-small.bin")


def test_cleanup_switch_persists(tmp_path, monkeypatch):
    _stub(monkeypatch)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    sw = _find(root, "switch-cleanup")
    sw.set_active(not sw.get_active())
    assert load(ctx.config_path).cleanup == sw.get_active()


def test_ollama_model_entry_does_not_save_on_every_keystroke(tmp_path, monkeypatch):
    _stub(monkeypatch)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    entry = _find(root, "entry-ollama-model")
    entry.set_text("llama3:8b")
    assert load(ctx.config_path).ollama_model != "llama3:8b"


def test_ollama_model_entry_persists_on_activate(tmp_path, monkeypatch):
    _stub(monkeypatch)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    entry = _find(root, "entry-ollama-model")
    entry.set_text("llama3:8b")
    entry.emit("activate")
    assert load(ctx.config_path).ollama_model == "llama3:8b"


def test_ollama_model_entry_persists_on_focus_leave(tmp_path, monkeypatch):
    _stub(monkeypatch)
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
    _stub(monkeypatch)
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    entry = _find(root, "entry-ollama-model")
    saves = []
    real_save = ctx.save
    monkeypatch.setattr(ctx, "save", lambda **kw: (saves.append(kw), real_save(**kw))[1])
    entry.emit("activate")  # no change made
    assert saves == []


def test_badge_updates_from_probe_thread(tmp_path, monkeypatch):
    _stub(monkeypatch)  # installed includes default qwen3:1.7b
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    badge = _find(root, "ollama-badge")
    _pump(1.0)
    assert badge.get_label() == "connected"


def test_pull_pill_shown_when_model_not_installed(tmp_path, monkeypatch):
    _stub(monkeypatch, installed=[])  # entered model not present -> offer pull
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    _pump(1.0)
    assert _find(root, "pull-row").get_visible()
    assert "qwen3:1.7b" in _find(root, "pull-model").get_label()


def test_pull_pill_hidden_when_installed(tmp_path, monkeypatch):
    _stub(monkeypatch, installed=["qwen3:1.7b"])
    ctx = _ctx(tmp_path)
    root = models.build(ctx)
    _pump(1.0)
    assert not _find(root, "pull-row").get_visible()
