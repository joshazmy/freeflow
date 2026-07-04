"""Platform ABC: OS-specific recording, delivery, media control and key-watching.

Linux (Wayland) is implemented in linux.py. macOS is planned (see docs/MACOS.md).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from freeflow.config import Config


class Platform(ABC):
    @abstractmethod
    def record_start(self, wav_path: str) -> None:
        """Start recording microphone audio to wav_path (16k mono s16)."""

    @abstractmethod
    def record_stop(self) -> None:
        """Stop recording; must flush a valid WAV header before returning."""

    @abstractmethod
    def deliver(self, text: str, cfg: "Config") -> None:
        """Insert text at the cursor (clipboard+paste, or per-char typing fallback)."""

    @abstractmethod
    def press_enter(self) -> None:
        """Send an Enter keypress."""

    @abstractmethod
    def media_pause(self) -> bool:
        """Pause media if something is playing. Returns True if it paused something."""

    @abstractmethod
    def media_resume(self) -> None:
        """Resume media previously paused by media_pause()."""

    @abstractmethod
    def watch_keys(self, cfg: "Config", on_start: Callable[[], None], on_stop: Callable[[], None]) -> None:
        """Blocking loop watching for the trigger chord.

        Hold semantics: full chord down -> on_start(); any chord key up -> on_stop().
        Hands-free (cfg.hands_free): two quick full-chord taps (each held <0.3s, gap
        <0.4s) toggle continuous mode -- on_start() fires and stays active; the next
        single chord tap calls on_stop() and exits toggle mode.
        """
