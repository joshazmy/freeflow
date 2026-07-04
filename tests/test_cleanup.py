"""Tests for freeflow.cleanup. Unit tests mock urllib; integration tests hit real Ollama."""
import io
import json
import os
import socket
import urllib.error

import pytest

from freeflow import cleanup
from freeflow.config import Config


def _mock_response(content):
    """Fake urlopen context manager returning an Ollama /api/chat body."""
    payload = json.dumps({"message": {"content": content}}).encode()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return payload

    def _urlopen(req, timeout=None):
        return _Resp()

    return _urlopen


CFG = Config()


# ---------- unit (mocked) ----------

def test_degrade_on_timeout(monkeypatch):
    def boom(req, timeout=None):
        raise socket.timeout("timed out")
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", boom)
    assert cleanup.clean("raw text here", "neutral", CFG) == "raw text here"


def test_degrade_on_http_error(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", boom)
    assert cleanup.clean("raw text here", "neutral", CFG) == "raw text here"


def test_degrade_on_garbage_response(monkeypatch):
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"not json at all"
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", lambda req, timeout=None: _Resp())
    assert cleanup.clean("raw text here", "neutral", CFG) == "raw text here"


def test_think_block_stripped(monkeypatch):
    monkeypatch.setattr(cleanup.urllib.request, "urlopen",
                        _mock_response("<think>reasoning...</think>Hello, world."))
    assert cleanup.clean("hello comma world period", "neutral", CFG) == "Hello, world."


def test_sanity_guard_too_long(monkeypatch):
    monkeypatch.setattr(cleanup.urllib.request, "urlopen",
                        _mock_response("x" * 500))
    assert cleanup.clean("short", "neutral", CFG) == "short"


def test_sanity_guard_too_short(monkeypatch):
    long_in = "this is a reasonably long sentence that should be cleaned normally"
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", _mock_response("hi"))
    assert cleanup.clean(long_in, "neutral", CFG) == long_in


def test_sanity_guard_empty(monkeypatch):
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", _mock_response("   "))
    assert cleanup.clean("some real input", "neutral", CFG) == "some real input"


def test_empty_input_short_circuits(monkeypatch):
    def fail(req, timeout=None):
        raise AssertionError("should not call the model on empty input")
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", fail)
    assert cleanup.clean("   ", "neutral", CFG) == "   "


def test_prompt_contains_hint_words(monkeypatch):
    captured = {}

    def spy(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _mock_response("Deploy Hyprland now.")(req, timeout)

    monkeypatch.setattr(cleanup.urllib.request, "urlopen", spy)
    cleanup.clean("deploy hyprland now", "neutral", CFG, hint_words=["Hyprland", "Wayland"])
    system = captured["body"]["messages"][0]["content"]
    assert "Hyprland" in system and "Wayland" in system


def test_think_flag_and_model_sent(monkeypatch):
    captured = {}

    def spy(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _mock_response("Hello, world.")(req, timeout)

    monkeypatch.setattr(cleanup.urllib.request, "urlopen", spy)
    cleanup.clean("hello comma world period", "neutral", CFG)
    body = captured["body"]
    assert body["think"] is False
    assert body["stream"] is False
    assert body["model"] == CFG.ollama_model


def test_never_raises(monkeypatch):
    # Contract: cleanup must NEVER raise — even an unexpected error degrades to raw text.
    def boom(req, timeout=None):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", boom)
    assert cleanup.clean("some real input", "neutral", CFG) == "some real input"


# ---------- integration (real Ollama) ----------

pytestmark_integration = pytest.mark.skipif(
    os.environ.get("FREEFLOW_INTEGRATION") != "1",
    reason="set FREEFLOW_INTEGRATION=1 to run real-Ollama tests",
)


@pytest.fixture(scope="module")
def warm_ollama():
    """Warm the model so the first real cleanup is not slow enough to time out."""
    cfg = Config(cleanup_timeout=30.0)
    cleanup.clean("hello comma world period", "neutral", cfg)
    return cfg


def _norm(s):
    return s.lower()


@pytest.mark.integration
@pytestmark_integration
def test_int_filler_removal(warm_ollama):
    out = cleanup.clean("um so basically can you uh send the the file tomorrow",
                        "neutral", warm_ollama)
    low = _norm(out)
    assert "send the file tomorrow" in low
    assert "um " not in low and not low.startswith("um")
    assert "uh " not in low


@pytest.mark.integration
@pytestmark_integration
def test_int_backtrack(warm_ollama):
    out = cleanup.clean("we should budget 50K for this actually make that 75K",
                        "neutral", warm_ollama)
    low = _norm(out)
    assert "75k" in low
    assert "50k" not in low


@pytest.mark.integration
@pytestmark_integration
def test_int_non_correction_actually_preserved(warm_ollama):
    out = cleanup.clean("honestly I actually enjoyed the movie a lot", "neutral", warm_ollama)
    low = _norm(out)
    assert "enjoyed the movie" in low


@pytest.mark.integration
@pytestmark_integration
def test_int_spoken_punctuation(warm_ollama):
    out = cleanup.clean("hello comma world period", "neutral", warm_ollama)
    low = _norm(out)
    assert "," in out and "." in out
    assert "comma" not in low
    assert "period" not in low
