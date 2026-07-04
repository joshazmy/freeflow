import signal
import subprocess

import pytest

from freeflow.overlay import Overlay


class FakeProc:
    def __init__(self, returncode=None):
        self.returncode = returncode
        self.signals = []
        self.waited = False
        self.killed = False

    def poll(self):
        return self.returncode

    def send_signal(self, sig):
        self.signals.append(sig)

    def wait(self, timeout=None):
        self.waited = True

    def kill(self):
        self.killed = True


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    import freeflow.overlay as overlay_mod
    monkeypatch.setattr(overlay_mod.time, "sleep", lambda *_: None)


def test_auto_mode_spawns_pill(monkeypatch):
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeProc(returncode=None)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    ov = Overlay("auto")
    ov.listening()

    assert captured["cmd"][1:] == ["-m", "freeflow.pill", "listening"]
    assert ov.mode == "auto"


def test_auto_mode_falls_back_on_early_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: FakeProc(returncode=3))
    notified = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: notified.append(cmd))

    ov = Overlay("auto")
    ov.listening()

    assert ov.mode == "notify"
    assert notified and notified[0][0] == "notify-send"


def test_processing_sends_sigusr1(monkeypatch):
    proc = FakeProc(returncode=None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: proc)
    ov = Overlay("auto")
    ov.listening()
    ov.processing()
    assert signal.SIGUSR1 in proc.signals


def test_done_sends_sigterm(monkeypatch):
    proc = FakeProc(returncode=None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: proc)
    ov = Overlay("auto")
    ov.listening()
    ov.done()
    assert signal.SIGTERM in proc.signals
    assert proc.waited
    assert ov._proc is None


def test_notify_mode_calls_notify_send(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: calls.append(cmd))
    ov = Overlay("notify")
    ov.listening()
    ov.processing()
    ov.done()
    assert len(calls) == 1
    assert calls[0][0] == "notify-send"


def test_off_mode_is_silent(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not be called")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    ov = Overlay("off")
    ov.listening()
    ov.processing()
    ov.done()
    # error() still notifies unless mode is off per contract -> off means silent even for error
    ov.error("oops")


def test_error_notifies_in_notify_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: calls.append(cmd))
    ov = Overlay("notify")
    ov.error("boom")
    assert calls and calls[0][0] == "notify-send"


def test_methods_never_raise_even_when_popen_explodes(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no gtk")

    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    ov = Overlay("auto")
    ov.listening()
    ov.processing()
    ov.done()
    ov.error("x")
    ov.close()
