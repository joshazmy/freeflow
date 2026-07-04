"""Tests for freeflow.engine: process() is pure and fully mocked here; sibling modules
(dictionary/context/cleanup/transcribe/overlay/platform) are monkeypatched."""
from __future__ import annotations

from freeflow import cleanup, context, engine, transcribe
from freeflow.config import Config
from freeflow.engine import Engine


class FakeDictionary:
    def __init__(self, path):
        self.path = path

    @property
    def words(self):
        return ["Hyprland"]

    def apply(self, text):
        return text.replace("hyperland", "Hyprland")


class FakePlatform:
    def __init__(self):
        self.recorded = False
        self.delivered = None
        self.enter_pressed = False
        self.media_paused = False
        self.media_resumed = False

    def record_start(self, wav_path):
        self.recorded = True

    def record_stop(self):
        pass

    def deliver(self, text, cfg):
        self.delivered = text

    def press_enter(self):
        self.enter_pressed = True

    def media_pause(self):
        self.media_paused = True
        return True

    def media_resume(self):
        self.media_resumed = True

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


def make_engine(monkeypatch, cfg=None, wav_size=100_000):
    cfg = cfg or Config()
    monkeypatch.setattr("freeflow.engine.get_platform", lambda: FakePlatform())
    monkeypatch.setattr("freeflow.engine.Overlay", FakeOverlay)
    monkeypatch.setattr("freeflow.engine.Dictionary", FakeDictionary)
    monkeypatch.setattr(context, "active_app", lambda: ("kitty", "term"))
    monkeypatch.setattr(context, "tone_for", lambda app, title, cfg: "neutral")
    eng = Engine(cfg)
    return eng


# -- process() --------------------------------------------------------------

def test_process_detects_press_enter(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False))
    final, flag = eng.process("send the email press enter")
    assert flag is True
    assert final == "send the email"


def test_process_detects_hit_enter_with_period(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False))
    final, flag = eng.process("submit the form hit enter.")
    assert flag is True
    assert final == "submit the form"


def test_process_no_press_enter(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False))
    final, flag = eng.process("just some text")
    assert flag is False
    assert final == "just some text"


def test_process_cleanup_disabled_converts_newlines(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False))
    final, _ = eng.process("hello new line world new paragraph done")
    assert final == "hello \n world \n\n done"


def test_process_cleanup_enabled_does_not_convert_newlines_itself(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=True))
    monkeypatch.setattr(cleanup, "clean", lambda text, tone, cfg, hint_words=(): text)
    final, _ = eng.process("hello new line world")
    assert final == "hello new line world"  # cleanup (mocked passthrough) owns this, not process()


def test_process_dictionary_applied(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False))
    final, _ = eng.process("open hyperland now")
    assert final == "open Hyprland now"


def test_process_cleanup_degrade_passthrough(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=True))
    monkeypatch.setattr(cleanup, "clean", lambda text, tone, cfg, hint_words=(): text)
    final, _ = eng.process("raw text unchanged")
    assert final == "raw text unchanged"


# -- _stop() pipeline ---------------------------------------------------------

def test_stop_drops_short_clip(monkeypatch, tmp_path):
    eng = make_engine(monkeypatch)
    eng.wav_path = str(tmp_path / "rec.wav")
    (tmp_path / "rec.wav").write_bytes(b"\x00" * 10)  # well under MIN_WAV_BYTES
    called = []
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **kw: called.append(1) or "text")
    eng._stop()
    assert called == []
    assert eng.platform.delivered is None
    assert "done" in eng.overlay.states


def test_stop_drops_hallucination(monkeypatch, tmp_path):
    eng = make_engine(monkeypatch)
    eng.wav_path = str(tmp_path / "rec.wav")
    (tmp_path / "rec.wav").write_bytes(b"\x00" * 50_000)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **kw: "thank you.")
    eng._stop()
    assert eng.platform.delivered is None


def test_stop_full_pipeline_delivers_and_presses_enter(monkeypatch, tmp_path):
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False))
    eng.wav_path = str(tmp_path / "rec.wav")
    (tmp_path / "rec.wav").write_bytes(b"\x00" * 50_000)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **kw: "send it press enter")
    eng._stop()
    assert eng.platform.delivered == "send it"
    assert eng.platform.enter_pressed is True
    assert eng.overlay.states[-1] == "done"
    assert eng.platform.media_resumed is True


def test_start_records_before_showing_overlay(monkeypatch):
    """Recording must never wait on the overlay -- record_start fires first."""
    eng = make_engine(monkeypatch)
    calls = []
    eng.platform.record_start = lambda wav_path: calls.append("record_start")
    eng.overlay.listening = lambda: calls.append("listening")
    eng._start()
    assert calls == ["record_start", "listening"]


def test_start_failure_resumes_media_and_hides_overlay(monkeypatch):
    eng = make_engine(monkeypatch, cfg=Config(media_pause=True))

    def boom(wav_path):
        raise RuntimeError("no mic")

    eng.platform.record_start = boom
    eng._start()
    assert eng.platform.media_paused is True
    assert eng.platform.media_resumed is True
    assert "done" in eng.overlay.states


def test_stop_empty_text_does_not_deliver(monkeypatch, tmp_path):
    # "press enter" alone is stripped down to "" by process() -- must not deliver/press enter.
    eng = make_engine(monkeypatch, cfg=Config(cleanup=False))
    eng.wav_path = str(tmp_path / "rec.wav")
    (tmp_path / "rec.wav").write_bytes(b"\x00" * 50_000)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **kw: "press enter")
    eng._stop()
    assert eng.platform.delivered is None
    assert eng.platform.enter_pressed is False
    assert any(s.startswith("error:") for s in eng.overlay.states)


def test_stop_pipeline_exception_never_raises(monkeypatch, tmp_path):
    eng = make_engine(monkeypatch)
    eng.wav_path = str(tmp_path / "rec.wav")
    (tmp_path / "rec.wav").write_bytes(b"\x00" * 50_000)

    def boom(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(transcribe, "transcribe", boom)
    eng._stop()  # must not raise
    assert any(s.startswith("error:") for s in eng.overlay.states)
    assert eng.overlay.states[-1] == "done"
