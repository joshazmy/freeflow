"""Linux (Wayland) platform adapter.

Ports the proven logic from ~/.local/share/whisper-dictation/listen.py:
recording via pw-record against the pactl default source (SIGINT flush for a
valid WAV header), delivery via wl-copy + ydotool Ctrl+V paste (per-char
ydotool type fallback), media pause/resume via playerctl (only if something
was actually playing), and a chord watcher over evdev that skips our own
ydotool/virtual injector device and tolerates device unplug.
"""
from __future__ import annotations

import os
import select
import signal
import subprocess
import time
from typing import TYPE_CHECKING, Callable

import evdev
from evdev import ecodes

from freeflow.platform.base import Platform

if TYPE_CHECKING:
    from freeflow.config import Config

os.environ.setdefault("YDOTOOL_SOCKET", "/run/ydotoold.socket")


def _run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=False, **kw)
    except FileNotFoundError:
        return None


class LinuxPlatform(Platform):
    def __init__(self) -> None:
        self._rec: subprocess.Popen | None = None
        self._media_was_paused = False

    # -- recording ---------------------------------------------------------

    def record_start(self, wav_path: str) -> None:
        try:
            os.remove(wav_path)
        except FileNotFoundError:
            pass
        src = ""
        r = _run(["pactl", "get-default-source"], capture_output=True, text=True, timeout=2)
        if r:
            src = r.stdout.strip()
        cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16"]
        if src:
            cmd += ["--target", src]
        cmd += [wav_path]
        self._rec = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def record_stop(self) -> None:
        if not self._rec:
            return
        self._rec.send_signal(signal.SIGINT)  # flush a valid WAV header (returns at once)
        try:
            self._rec.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            self._rec.kill()
        self._rec = None

    # -- delivery ------------------------------------------------------------

    def deliver(self, text: str, cfg: "Config") -> None:
        out = text + " "
        if cfg.paste:
            r = _run(["wl-copy"], input=out.encode())
            if r is not None and r.returncode == 0:
                time.sleep(0.015)  # let wl-copy own the selection before pasting
                # Ctrl down, V down, V up, Ctrl up  (29=LEFTCTRL, 47=V)
                _run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])
                return
        _run(["ydotool", "type", "--key-delay", "2", "--", out])

    def press_enter(self) -> None:
        _run(["ydotool", "key", "28:1", "28:0"])

    # -- media ---------------------------------------------------------------

    def media_pause(self) -> bool:
        self._media_was_paused = False
        r = _run(["playerctl", "status"], capture_output=True, text=True, timeout=1)
        if r and r.stdout.strip() == "Playing":
            _run(["playerctl", "pause"])
            self._media_was_paused = True
        return self._media_was_paused

    def media_resume(self) -> None:
        if self._media_was_paused:
            _run(["playerctl", "play"])
            self._media_was_paused = False

    # -- chord watching --------------------------------------------------------

    @staticmethod
    def _find_keyboards(chord: frozenset[int]) -> list["evdev.InputDevice"]:
        devs = []
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
            except OSError:
                continue
            name = d.name.lower()
            if "ydotool" in name or "virtual" in name:
                continue  # skip our own injector to avoid feedback loops
            keys = set(d.capabilities().get(ecodes.EV_KEY, []))
            if chord <= keys:
                devs.append(d)
        return devs

    def watch_keys(self, cfg: "Config", on_start: Callable[[], None], on_stop: Callable[[], None]) -> None:
        chord = frozenset(getattr(ecodes, k.strip()) for k in cfg.keys.split(",") if k.strip())
        devs = self._find_keyboards(chord)
        if not devs:
            raise RuntimeError("No keyboard exposing the trigger chord found")
        fdmap = {d.fd: d for d in devs}

        held: set[int] = set()          # chord keys currently held, across all devices
        recording = False                # a dictation is currently in progress
        toggle_mode = False              # hands-free continuous mode active
        chord_press_time: float | None = None   # monotonic time the chord last became fully held
        last_short_tap_end: float | None = None  # end time of the previous qualifying short tap

        while fdmap:
            r, _, _ = select.select(list(fdmap), [], [])
            for fd in r:
                d = fdmap.get(fd)
                if not d:
                    continue
                try:
                    for ev in d.read():
                        if ev.type != ecodes.EV_KEY or ev.code not in chord:
                            continue
                        now = time.monotonic()

                        if ev.value == 1:  # press
                            was_full = held >= chord
                            held.add(ev.code)
                            if held >= chord and not was_full:
                                chord_press_time = now
                                if not recording:
                                    on_start()
                                    recording = True
                                # else: already recording (toggle mode) -- this
                                # press is the tap that will end it on release.

                        elif ev.value == 0:  # release -> chord broken
                            held.discard(ev.code)
                            if chord_press_time is None:
                                continue  # chord was never fully held this cycle
                            hold_dur = now - chord_press_time
                            chord_press_time = None

                            if toggle_mode:
                                on_stop()
                                recording = False
                                toggle_mode = False
                                last_short_tap_end = None
                                continue

                            is_short = cfg.hands_free and hold_dur < 0.3
                            if (
                                is_short
                                and last_short_tap_end is not None
                                and (now - last_short_tap_end) < 0.4
                            ):
                                # second quick tap: enter hands-free toggle mode,
                                # recording (already started) continues.
                                toggle_mode = True
                                last_short_tap_end = None
                            else:
                                on_stop()
                                recording = False
                                last_short_tap_end = now if is_short else None
                        # value == 2 (autorepeat) ignored
                except OSError:
                    fdmap.pop(fd, None)  # device unplugged
                    held.clear()
                    if recording:
                        on_stop()
                        recording = False
                    toggle_mode = False
                    chord_press_time = None
                    last_short_tap_end = None
