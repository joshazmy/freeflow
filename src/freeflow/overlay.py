"""Dictation status overlay: pill subprocess (auto), notify-send (notify), or silent (off)."""
import signal
import subprocess
import sys


def _notify(title: str, ms: int = 1500) -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "Freeflow", "-t", str(ms), title],
            timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        pass


class Overlay:
    def __init__(self, mode: str):
        self.mode = mode
        self._proc: subprocess.Popen | None = None

    # -- pill lifecycle -----------------------------------------------
    def _spawn_pill(self) -> None:
        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-m", "freeflow.pill", "listening"]
            )
        except (OSError, ValueError):
            self._proc = None
            self.mode = "notify"
            return
        # Don't block the hot path waiting on the pill's health -- a non-blocking poll
        # catches an immediate exec failure; anything slower is caught in processing()/done().
        if self._proc.poll() not in (None, 0):
            self._proc = None
            self.mode = "notify"

    def _check_pill_alive(self) -> None:
        """Deferred health check: if the pill process has since exited nonzero, fall
        back to notify for the rest of the session."""
        if self._proc is not None and self._proc.poll() not in (None, 0):
            self._proc = None
            self.mode = "notify"

    def _signal_pill(self, sig: int) -> None:
        if self._proc is None:
            return
        try:
            self._proc.send_signal(sig)
        except (OSError, ProcessLookupError):
            self._proc = None

    # -- public API -----------------------------------------------------
    def listening(self) -> None:
        try:
            if self.mode == "off":
                return
            if self.mode == "auto":
                self._spawn_pill()
                if self.mode == "auto":
                    return
            if self.mode == "notify":
                _notify("\U0001F399 Listening…", 1500)
        except Exception:
            pass

    def processing(self) -> None:
        try:
            if self.mode == "off":
                return
            if self.mode == "auto":
                self._check_pill_alive()
                if self.mode == "auto":
                    self._signal_pill(signal.SIGUSR1)
                else:
                    _notify("\U0001F399 Processing…", 1500)
        except Exception:
            pass

    def done(self) -> None:
        try:
            if self.mode == "off":
                return
            if self.mode == "auto":
                self._check_pill_alive()
            if self.mode == "auto" and self._proc is not None:
                proc = self._proc
                self._proc = None
                try:
                    proc.send_signal(signal.SIGTERM)
                    proc.wait(timeout=0.5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        proc.kill()
                    except OSError:
                        pass
        except Exception:
            pass

    def error(self, msg: str) -> None:
        try:
            if self.mode == "off":
                return
            _notify(f"Freeflow error: {msg}", 3000)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.done()
        except Exception:
            pass
