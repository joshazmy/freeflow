"""Tests for freeflow.platform.linux: everything (subprocess, evdev) is mocked."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest
from evdev import ecodes

from freeflow.config import Config
from freeflow.platform.linux import LinuxPlatform


class FakeCompleted:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class FakeEvent:
    def __init__(self, code, value, type_=ecodes.EV_KEY):
        self.type = type_
        self.code = code
        self.value = value


class FakeDevice:
    """Stands in for an evdev.InputDevice; each read() call returns one queued
    batch of events, then raises OSError once the queue is exhausted (simulating
    the device being unplugged) so the blocking watch_keys loop can terminate."""

    def __init__(self, fd, name, keys, event_batches):
        self.fd = fd
        self.name = name
        self._keys = keys
        self._batches = list(event_batches)

    def capabilities(self):
        return {ecodes.EV_KEY: self._keys}

    def read(self):
        if self._batches:
            return self._batches.pop(0)
        raise OSError("device unplugged")


CHORD_NAMES = "KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT"
CTRL, ALT, SHIFT = ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT, ecodes.KEY_LEFTSHIFT


def make_cfg(**overrides):
    return Config(**{"keys": CHORD_NAMES, "hands_free": True, "paste": True, **overrides})


def install_fake_device(monkeypatch, events, keys=(CTRL, ALT, SHIFT)):
    dev = FakeDevice(5, "Test Keyboard", set(keys), [[e] for e in events])
    monkeypatch.setattr("freeflow.platform.linux.evdev.list_devices", lambda: ["/dev/input/event0"])
    monkeypatch.setattr("freeflow.platform.linux.evdev.InputDevice", lambda path: dev)
    monkeypatch.setattr("freeflow.platform.linux.select.select", lambda r, w, x: (r, [], []))
    return dev


# -- delivery -----------------------------------------------------------------

def test_deliver_paste_success(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[0] == "wl-copy":
            return FakeCompleted(returncode=0)
        return FakeCompleted(returncode=0)

    monkeypatch.setattr("freeflow.platform.linux._run", fake_run)
    monkeypatch.setattr("freeflow.platform.linux.time.sleep", lambda s: None)
    LinuxPlatform().deliver("hello", make_cfg(paste=True))

    assert calls[0][0] == "wl-copy"
    assert calls[1] == ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]


def test_deliver_falls_back_to_type_when_wlcopy_fails(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[0] == "wl-copy":
            return FakeCompleted(returncode=1)
        return FakeCompleted(returncode=0)

    monkeypatch.setattr("freeflow.platform.linux._run", fake_run)
    LinuxPlatform().deliver("hello", make_cfg(paste=True))

    assert calls[-1][:2] == ["ydotool", "type"]


def test_press_enter(monkeypatch):
    calls = []
    monkeypatch.setattr("freeflow.platform.linux._run", lambda cmd, **kw: calls.append(cmd))
    LinuxPlatform().press_enter()
    assert calls == [["ydotool", "key", "28:1", "28:0"]]


# -- media ----------------------------------------------------------------

def test_media_pause_when_playing(monkeypatch):
    def fake_run(cmd, **kw):
        if cmd[:2] == ["playerctl", "status"]:
            return FakeCompleted(stdout="Playing")
        return FakeCompleted()

    monkeypatch.setattr("freeflow.platform.linux._run", fake_run)
    plat = LinuxPlatform()
    assert plat.media_pause() is True


def test_media_resume_only_if_was_paused(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["playerctl", "status"]:
            return FakeCompleted(stdout="Stopped")
        return FakeCompleted()

    monkeypatch.setattr("freeflow.platform.linux._run", fake_run)
    plat = LinuxPlatform()
    assert plat.media_pause() is False
    calls.clear()
    plat.media_resume()
    assert calls == []  # nothing was paused, so no playerctl play call


# -- recording --------------------------------------------------------------

def test_record_start_stop(monkeypatch, tmp_path):
    popen_calls = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            popen_calls.append(cmd)
            self.sent = None

        def send_signal(self, sig):
            self.sent = sig

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr("freeflow.platform.linux.subprocess.Popen", FakePopen)
    monkeypatch.setattr(
        "freeflow.platform.linux._run",
        lambda cmd, **kw: FakeCompleted(stdout="my.source"),
    )
    plat = LinuxPlatform()
    wav = str(tmp_path / "rec.wav")
    plat.record_start(wav)
    assert "--target" in popen_calls[0] and "my.source" in popen_calls[0]
    plat.record_stop()
    assert plat._rec is None


# -- chord watching --------------------------------------------------------

def test_find_keyboards_skips_virtual(monkeypatch):
    real = FakeDevice(3, "Real Keyboard", {CTRL, ALT, SHIFT}, [])
    virt = FakeDevice(4, "ydotool virtual device", {CTRL, ALT, SHIFT}, [])
    monkeypatch.setattr(
        "freeflow.platform.linux.evdev.list_devices",
        lambda: ["/dev/input/event0", "/dev/input/event1"],
    )
    devs = iter([real, virt])
    monkeypatch.setattr("freeflow.platform.linux.evdev.InputDevice", lambda path: next(devs))

    found = LinuxPlatform._find_keyboards(frozenset({CTRL, ALT, SHIFT}))
    assert found == [real]


def test_watch_keys_hold_then_release_stops(monkeypatch):
    events = [
        FakeEvent(CTRL, 1),
        FakeEvent(ALT, 1),
        FakeEvent(SHIFT, 1),   # chord fully down -> on_start
        FakeEvent(SHIFT, 0),   # release -> on_stop
    ]
    install_fake_device(monkeypatch, events)
    starts, stops = [], []
    LinuxPlatform().watch_keys(make_cfg(), lambda: starts.append(1), lambda: stops.append(1))
    assert len(starts) == 1
    assert len(stops) == 1


def test_watch_keys_hands_free_double_tap_toggle(monkeypatch):
    events = [
        FakeEvent(CTRL, 1), FakeEvent(ALT, 1), FakeEvent(SHIFT, 1),  # tap1 down -> on_start #1
        FakeEvent(SHIFT, 0),                                         # tap1 up (short) -> on_stop #1
        FakeEvent(SHIFT, 1),                                         # tap2 down -> on_start #2
        FakeEvent(CTRL, 0),                                          # tap2 up (short, quick) -> enters toggle
        FakeEvent(CTRL, 1),                                          # tap3 down (exit toggle) -> no on_start
        FakeEvent(ALT, 0),                                           # tap3 up -> on_stop #2, exits toggle
    ]
    install_fake_device(monkeypatch, events)
    starts, stops = [], []
    LinuxPlatform().watch_keys(make_cfg(hands_free=True), lambda: starts.append(1), lambda: stops.append(1))
    assert len(starts) == 2
    assert len(stops) == 2


def test_watch_keys_no_devices_raises(monkeypatch):
    monkeypatch.setattr("freeflow.platform.linux.evdev.list_devices", lambda: [])
    with pytest.raises(RuntimeError):
        LinuxPlatform().watch_keys(make_cfg(), lambda: None, lambda: None)
