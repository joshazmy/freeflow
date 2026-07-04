import subprocess
import types

import pytest

from freeflow import transcribe as tmod


class FakeCfg:
    def __init__(self, server="127.0.0.1:8765", whisper_bin="/bin/whisper-cli",
                 model_path="/models/m.bin", language="en", threads=8):
        self.server = server
        self.whisper_bin = whisper_bin
        self.model_path = model_path
        self.language = language
        self.threads = threads


@pytest.fixture
def wav(tmp_path):
    p = tmp_path / "rec.wav"
    p.write_bytes(b"\x00" * 100)
    return str(p)


def test_server_success(monkeypatch, wav):
    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b"  hello   world  "

    monkeypatch.setattr(tmod.urllib.request, "urlopen", lambda req, timeout=None: FakeResp())

    def fail_run(*a, **k):
        raise AssertionError("should not fall back to CLI")
    monkeypatch.setattr(tmod.subprocess, "run", fail_run)

    out = tmod.transcribe(wav, FakeCfg())
    assert out == "hello world"


def test_server_down_falls_back_to_cli(monkeypatch, wav):
    def bad_urlopen(req, timeout=None):
        raise tmod.urllib.error.URLError("connection refused")
    monkeypatch.setattr(tmod.urllib.request, "urlopen", bad_urlopen)

    def fake_run(cmd, **kw):
        assert cmd[0] == "/bin/whisper-cli"
        return types.SimpleNamespace(stdout="cli text here", returncode=0)
    monkeypatch.setattr(tmod.subprocess, "run", fake_run)

    out = tmod.transcribe(wav, FakeCfg())
    assert out == "cli text here"


def test_no_server_configured_goes_straight_to_cli(monkeypatch, wav):
    def fail_urlopen(*a, **k):
        raise AssertionError("should not touch network when server disabled")
    monkeypatch.setattr(tmod.urllib.request, "urlopen", fail_urlopen)

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(stdout="cli only", returncode=0)
    monkeypatch.setattr(tmod.subprocess, "run", fake_run)

    out = tmod.transcribe(wav, FakeCfg(server=""))
    assert out == "cli only"


def test_total_failure_returns_empty(monkeypatch, wav):
    def bad_urlopen(req, timeout=None):
        raise tmod.urllib.error.URLError("down")
    monkeypatch.setattr(tmod.urllib.request, "urlopen", bad_urlopen)

    def bad_run(cmd, **kw):
        raise FileNotFoundError("no whisper-cli")
    monkeypatch.setattr(tmod.subprocess, "run", bad_run)

    out = tmod.transcribe(wav, FakeCfg())
    assert out == ""


def test_hint_words_plumbed_into_cli_prompt(monkeypatch, wav):
    def bad_urlopen(*a, **k):
        raise tmod.urllib.error.URLError("down")
    monkeypatch.setattr(tmod.urllib.request, "urlopen", bad_urlopen)

    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return types.SimpleNamespace(stdout="text", returncode=0)
    monkeypatch.setattr(tmod.subprocess, "run", fake_run)

    tmod.transcribe(wav, FakeCfg(), hint_words=["Hyprland", "Wispr"])
    assert "--prompt" in captured["cmd"]
    idx = captured["cmd"].index("--prompt")
    assert captured["cmd"][idx + 1] == "Hyprland Wispr"


def test_hint_words_plumbed_into_server_prompt(monkeypatch, wav):
    captured = {}

    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b"ok"

    def fake_urlopen(req, timeout=None):
        captured["body"] = req.data
        return FakeResp()
    monkeypatch.setattr(tmod.urllib.request, "urlopen", fake_urlopen)

    tmod.transcribe(wav, FakeCfg(), hint_words=["Hyprland"])
    assert b'name="prompt"' in captured["body"]
    assert b"Hyprland" in captured["body"]


def test_empty_server_response_falls_back_to_cli(monkeypatch, wav):
    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b"   "

    monkeypatch.setattr(tmod.urllib.request, "urlopen", lambda req, timeout=None: FakeResp())

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(stdout="fallback text", returncode=0)
    monkeypatch.setattr(tmod.subprocess, "run", fake_run)

    out = tmod.transcribe(wav, FakeCfg())
    assert out == "fallback text"


@pytest.mark.parametrize("text", [
    "you", "Thank you.", "BYE", "...", "okay.", "Thank you very much",
])
def test_hallucinations_detected(text):
    assert tmod.is_hallucination(text)


@pytest.mark.parametrize("text", [
    "hello world", "you are great", "thank you for the help",
])
def test_real_text_not_flagged(text):
    assert not tmod.is_hallucination(text)


def test_min_wav_bytes_matches_spec():
    assert tmod.MIN_WAV_BYTES == 44 + int(0.35 * 32000)
