"""Engine: wires platform + overlay + dictionary + sibling modules into one dictation pipeline.

process() is the pure, testable behavioral surface (no audio/subprocess calls). _start/_stop
drive the actual recording lifecycle and must never let one bad dictation kill the daemon.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile

from freeflow import cleanup, context, transcribe
from freeflow.config import Config
from freeflow.dictionary import Dictionary
from freeflow.overlay import Overlay
from freeflow.platform import get_platform

log = logging.getLogger("freeflow.engine")

# Trailing "press enter" / "hit enter", optional trailing period, case-insensitive.
_PRESS_ENTER_RE = re.compile(r"\s*(?:press|hit)\s+enter\.?\s*$", re.IGNORECASE)
# Spoken standalone punctuation words -- only applied when cfg.cleanup is off
# (cleanup's own prompt handles these when it's on).
_NEW_PARAGRAPH_RE = re.compile(r"\bnew paragraph\b", re.IGNORECASE)
_NEW_LINE_RE = re.compile(r"\bnew line\b", re.IGNORECASE)


class Engine:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.platform = get_platform()
        self.overlay = Overlay(cfg.overlay)
        self.dictionary = Dictionary(cfg.dictionary_path)
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
        if xdg_runtime:
            run_dir = os.path.join(xdg_runtime, "freeflow")
            os.makedirs(run_dir, mode=0o700, exist_ok=True)
        else:
            # No XDG_RUNTIME_DIR (e.g. not a login session) -- a predictable /tmp/freeflow
            # path would be guessable by other local users, so use a private mkdtemp instead.
            run_dir = tempfile.mkdtemp(prefix="freeflow-")
        self.wav_path = os.path.join(run_dir, "rec.wav")

    def run(self) -> None:
        self.platform.watch_keys(self.cfg, self._start, self._stop)

    def _start(self) -> None:
        media_paused = False
        try:
            if self.cfg.media_pause:
                media_paused = self.platform.media_pause()
            # Recording must never wait on the overlay -- start it first.
            self.platform.record_start(self.wav_path)
            self.overlay.listening()
        except Exception:
            log.exception("failed to start dictation")
            self.overlay.error("failed to start recording")
            self.overlay.done()
            if media_paused:
                self.platform.media_resume()

    def _stop(self) -> None:
        try:
            self.platform.record_stop()
            self.overlay.processing()

            size = os.path.getsize(self.wav_path) if os.path.exists(self.wav_path) else 0
            if size < transcribe.MIN_WAV_BYTES:
                return

            text = transcribe.transcribe(self.wav_path, self.cfg, hint_words=self.dictionary.words)
            if transcribe.is_hallucination(text):
                return

            final, do_press_enter = self.process(text)
            if not final.strip():
                self.overlay.error("no speech detected")
                return
            self.platform.deliver(final, self.cfg)
            if do_press_enter:
                self.platform.press_enter()
        except Exception:
            # One bad dictation must never kill the daemon.
            log.exception("dictation pipeline failed")
            self.overlay.error("dictation failed")
        finally:
            self.overlay.done()
            if self.cfg.media_pause:
                self.platform.media_resume()

    def process(self, raw: str) -> tuple[str, bool]:
        """Pure text pipeline: (final_text, press_enter). No audio/subprocess side effects."""
        text = raw
        do_press_enter = False

        m = _PRESS_ENTER_RE.search(text)
        if m:
            do_press_enter = True
            text = text[: m.start()].rstrip()

        if not self.cfg.cleanup:
            # cleanup's own prompt turns these into line breaks when it's enabled.
            text = _NEW_PARAGRAPH_RE.sub("\n\n", text)
            text = _NEW_LINE_RE.sub("\n", text)

        text = self.dictionary.apply(text)

        app_class, title = context.active_app()
        tone = context.tone_for(app_class, title, self.cfg)

        if self.cfg.cleanup:
            text = cleanup.clean(text, tone, self.cfg, hint_words=self.dictionary.words)

        return text, do_press_enter
