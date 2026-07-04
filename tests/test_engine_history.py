"""Tests for dictation-history recording wired into Engine._stop()."""
from __future__ import annotations

from freeflow import context, engine, transcribe
from freeflow.config import Config


class FakeDictionary:
    def __init__(self, path):
        self.path = path

    @property
    def words(self):
        return []

    def apply(self, text):
        return text


class FakePlatform:
    def __init__(self):
        self.delivered = None
        self.enter_pressed = False

    def record_start(self, wav_path):
        pass

    def record_stop(self):
        pass

    def deliver(self, text, cfg):
        self.delivered = text

    def press_enter(self):
        self.enter_pressed = True

    def media_pause(self):
        return False

    def media_resume(self):
        pass

    def watch_keys(self, cfg, on_start, on_stop):
        pass


class FakeOverlay:
    def __init__(self, mode):
        self.states = []

    def listening(self):
        self.states.append("listening")

    def processing(self):
        self.states.append("processing")

    def done(self):
        self.states.append("done")

    def error(self, msg):
        self.states.append(f"error:{msg}")

    def close(self):
        pass


class RecordingHistory:
    """Stand-in for freeflow.history.History that records append() calls."""

    instances = []

    def __init__(self, *a, **kw):
        self.entries = []
        RecordingHistory.instances.append(self)

    def append(self, **kwargs):
        self.entries.append(kwargs)


class BoomHistory:
    def __init__(self, *a, **kw):
        pass

    def append(self, **kwargs):
        raise RuntimeError("disk on fire")


def make_engine(monkeypatch, cfg=None):
    cfg = cfg or Config()
    monkeypatch.setattr("freeflow.engine.get_platform", lambda: FakePlatform())
    monkeypatch.setattr("freeflow.engine.Overlay", FakeOverlay)
    monkeypatch.setattr("freeflow.engine.Dictionary", FakeDictionary)
    monkeypatch.setattr(context, "active_app", lambda: ("slack", "title"))
    monkeypatch.setattr(context, "tone_for", lambda app, title, cfg: "formal")
    eng = engine.Engine(cfg)
    return eng


def _write_wav(tmp_path):
    p = tmp_path / "rec.wav"
    p.write_bytes(b"\x00" * 50_000)
    return str(p)


def test_stop_appends_history_entry(monkeypatch, tmp_path):
    RecordingHistory.instances = []
    monkeypatch.setattr(engine, "History", RecordingHistory)
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False, history=True))
    eng.wav_path = _write_wav(tmp_path)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **kw: "hello world")
    eng._stop()

    assert len(RecordingHistory.instances) == 1
    entries = RecordingHistory.instances[0].entries
    assert len(entries) == 1
    entry = entries[0]
    assert entry["raw"] == "hello world"
    assert entry["cleaned"] == "hello world"
    assert entry["app"] == "slack"
    assert entry["tone"] == "formal"
    assert isinstance(entry["ts"], float)
    assert eng.platform.delivered == "hello world"


def test_stop_history_disabled_appends_nothing(monkeypatch, tmp_path):
    RecordingHistory.instances = []
    monkeypatch.setattr(engine, "History", RecordingHistory)
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False, history=False))
    eng.wav_path = _write_wav(tmp_path)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **kw: "hello world")
    eng._stop()

    assert RecordingHistory.instances == []
    assert eng.platform.delivered == "hello world"


def test_stop_history_append_failure_does_not_break_delivery(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "History", BoomHistory)
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False, history=True))
    eng.wav_path = _write_wav(tmp_path)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **kw: "hello world")
    eng._stop()  # must not raise

    assert eng.platform.delivered == "hello world"
    assert eng.overlay.states[-1] == "done"
