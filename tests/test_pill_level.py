"""Unit tests for freeflow.pill's mic-level helpers and mic-capture fallback path.

pill.py only needs plain Gtk 4.0 to import (Gtk4LayerShell is loaded lazily inside
do_activate, see _load_layer_shell) so these tests run in-process without a real
layer-shell compositor or audio hardware."""
import struct
import subprocess

import pytest

from freeflow import pill


def _pcm(samples) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


# -- rms_level --------------------------------------------------------------

def test_rms_level_silence_is_zero():
    assert pill.rms_level(_pcm([0] * 1600)) == 0.0


def test_rms_level_empty_buffer_is_zero():
    assert pill.rms_level(b"") == 0.0


def test_rms_level_full_scale_square_wave_is_near_one():
    samples = [32767 if i % 2 == 0 else -32768 for i in range(1600)]
    assert pill.rms_level(_pcm(samples)) > 0.95


def test_rms_level_half_scale_square_wave_is_about_half():
    samples = [16384 if i % 2 == 0 else -16384 for i in range(1600)]
    level = pill.rms_level(_pcm(samples))
    assert 0.4 <= level <= 0.6


def test_rms_level_odd_length_buffer_does_not_crash():
    data = _pcm([2000] * 100) + b"\x01"  # trailing odd byte
    level = pill.rms_level(data)
    assert 0.0 <= level <= 1.0


def test_rms_level_clamped_to_one():
    # int16 min/max square wave can't exceed 1.0 after normalization.
    samples = [32767, -32768] * 800
    assert pill.rms_level(_pcm(samples)) <= 1.0


# -- smooth_level -------------------------------------------------------------

def test_smooth_level_jumps_up_immediately():
    assert pill.smooth_level(0.1, 0.9) == 0.9


def test_smooth_level_decays_towards_quieter_new_level():
    assert pill.smooth_level(1.0, 0.0) == pytest.approx(0.8)


def test_smooth_level_holds_steady_above_decayed_prev():
    assert pill.smooth_level(0.5, 0.41) == pytest.approx(0.41)


# -- mic capture spawn / fallback --------------------------------------------

def test_start_mic_capture_falls_back_silently_when_popen_raises(monkeypatch):
    def boom(*a, **k):
        raise OSError("no pw-record binary")
    monkeypatch.setattr(subprocess, "Popen", boom)

    p = pill.Pill()
    p._start_mic_capture()  # must not raise

    assert p.mic_proc is None
    assert p._mic_live is False


def test_start_mic_capture_spawns_pw_record(monkeypatch):
    import io

    calls = []

    class FakeProc:
        stdout = io.BytesIO(b"")  # EOF immediately -- reader thread exits clean

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    def fake_popen(cmd, **kw):
        calls.append(cmd)
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    p = pill.Pill()
    p._start_mic_capture()

    assert calls and calls[0][0] == "pw-record"
    assert p.mic_proc is not None


def test_stop_mic_capture_terminates_process_and_resets_state():
    class FakeProc:
        def __init__(self):
            self.terminated = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            pass

    p = pill.Pill()
    proc = FakeProc()
    p.mic_proc = proc
    p._mic_live = True
    p.mic_level = 0.7

    p._stop_mic_capture()

    assert proc.terminated
    assert p.mic_proc is None
    assert p._mic_live is False
    assert p.mic_level == 0.0


def test_stop_mic_capture_kills_on_terminate_failure():
    class FakeProc:
        def __init__(self):
            self.killed = False

        def terminate(self):
            raise OSError("already dead")

        def wait(self, timeout=None):
            pass

        def kill(self):
            self.killed = True

    p = pill.Pill()
    proc = FakeProc()
    p.mic_proc = proc

    p._stop_mic_capture()  # must not raise

    assert proc.killed
    assert p.mic_proc is None


def test_stop_mic_capture_is_a_noop_when_nothing_running():
    p = pill.Pill()
    p._stop_mic_capture()  # must not raise
    assert p.mic_proc is None


def test_apply_mic_level_smooths_and_marks_live():
    p = pill.Pill()
    p.mic_level = 0.5

    result = p._apply_mic_level(0.9)

    assert result is False  # one-shot GLib.idle_add callback
    assert p._mic_live is True
    assert p.mic_level == 0.9


def test_set_state_starts_capture_when_entering_listening(monkeypatch):
    started = []
    p = pill.Pill()
    p.state = "processing"
    p.area = None
    monkeypatch.setattr(p, "_start_mic_capture", lambda: started.append(True))

    p.set_state("listening")

    assert started == [True]
    assert p.state == "listening"


def test_set_state_stops_capture_when_leaving_listening(monkeypatch):
    stopped = []
    p = pill.Pill()
    p.state = "listening"
    p.area = None
    monkeypatch.setattr(p, "_stop_mic_capture", lambda: stopped.append(True))

    p.set_state("processing")

    assert stopped == [True]
    assert p.state == "processing"


def test_set_state_no_capture_toggle_on_same_state(monkeypatch):
    calls = []
    p = pill.Pill()
    p.state = "listening"
    p.area = None
    monkeypatch.setattr(p, "_start_mic_capture", lambda: calls.append("start"))
    monkeypatch.setattr(p, "_stop_mic_capture", lambda: calls.append("stop"))

    p.set_state("listening")

    assert calls == []
