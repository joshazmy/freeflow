"""Wispr-Flow-style pill overlay: python -m freeflow.pill [listening|processing].

GTK4 + gtk4-layer-shell. SIGUSR1 -> processing state, SIGTERM -> exit.
Exits with status 3 if gi / layer-shell setup is unavailable (caller falls back to notify).

While listening, bar heights are driven by real mic amplitude via a `pw-record`
subprocess (PipeWire allows concurrent capture streams, so this does not disturb
the engine's own recording). If pw-record can't be spawned or produces nothing,
the pill falls back silently to the placeholder animation -- it must never break.
"""
import math
import os
import random
import signal
import struct
import subprocess
import sys
import threading

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
except Exception:
    sys.exit(3)

WIDTH, HEIGHT = 72, 26
BAR_COUNT = 5
DOT_COUNT = 3
MIC_CHUNK_SAMPLES = 1600
MIC_CHUNK_BYTES = MIC_CHUNK_SAMPLES * 2  # 16-bit samples


def _load_layer_shell():
    """Return the Gtk4LayerShell module, or None if the typelib is unavailable."""
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell
        return Gtk4LayerShell
    except Exception:
        return None


def rms_level(chunk: bytes) -> float:
    """RMS of a little-endian int16 PCM buffer, normalized to 0..1. Never raises
    on odd-length or empty input."""
    n = len(chunk) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", chunk[: n * 2])
    mean_sq = sum(s * s for s in samples) / n
    return min(1.0, math.sqrt(mean_sq) / 32768.0)


def smooth_level(prev: float, new: float, decay: float = 0.8) -> float:
    """Attack-fast, decay-slow smoothing: jump straight to a louder level,
    ease down towards a quieter one."""
    return max(new, prev * decay)


class Pill(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.freeflow.pill")
        self.state = "listening"
        self.bar_heights = [6.0] * BAR_COUNT
        self.dot_phase = 0.0
        self.window = None
        self.mic_proc = None
        self.mic_level = 0.0
        self._mic_live = False

    def do_activate(self):
        Gtk4LayerShell = _load_layer_shell()
        if Gtk4LayerShell is None:
            os._exit(3)

        win = Gtk.ApplicationWindow(application=self)
        win.set_default_size(WIDTH, HEIGHT)

        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.BOTTOM, True)
        Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.BOTTOM, 28)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.NONE)

        area = Gtk.DrawingArea()
        area.set_content_width(WIDTH)
        area.set_content_height(HEIGHT)
        area.set_draw_func(self._draw, None)
        win.set_child(area)
        self.area = area
        self.window = win
        win.present()

        if self.state == "listening":
            self._start_mic_capture()

        GLib.timeout_add(80, self._tick)

    def _tick(self) -> bool:
        if self.state == "listening":
            if self._mic_live:
                base = 4 + self.mic_level * (HEIGHT - 12)
                self.bar_heights = [
                    max(4.0, base + random.uniform(-3, 3)) for _ in range(BAR_COUNT)
                ]
            else:
                self.bar_heights = [random.uniform(4, HEIGHT - 8) for _ in range(BAR_COUNT)]
        else:
            self.dot_phase += 0.3
        self.area.queue_draw()
        return True

    def _draw(self, area, cr, w, h, data):
        # Rounded dark pill background.
        radius = h / 2
        cr.set_source_rgba(0x1a / 255, 0x1a / 255, 0x1a / 255, 0.8)
        cr.arc(radius, radius, radius, math.pi / 2, 3 * math.pi / 2)
        cr.arc(w - radius, radius, radius, -math.pi / 2, math.pi / 2)
        cr.close_path()
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.9)
        if self.state == "listening":
            gap = w / (BAR_COUNT + 1)
            bar_w = 3
            for i, bh in enumerate(self.bar_heights):
                x = gap * (i + 1)
                cr.rectangle(x - bar_w / 2, h / 2 - bh / 2, bar_w, bh)
                cr.fill()
        else:
            gap = w / (DOT_COUNT + 1)
            for i in range(DOT_COUNT):
                x = gap * (i + 1)
                alpha = 0.3 + 0.7 * abs(math.sin(self.dot_phase + i * 1.0))
                cr.set_source_rgba(1, 1, 1, alpha)
                cr.arc(x, h / 2, 3, 0, 2 * math.pi)
                cr.fill()

    def set_state(self, state: str) -> None:
        if state == "listening" and self.state != "listening":
            self._start_mic_capture()
        elif state != "listening" and self.state == "listening":
            self._stop_mic_capture()
        self.state = state
        if self.area is not None:
            self.area.queue_draw()

    # -- mic capture (own PipeWire stream, never touches the engine's) --------
    def _start_mic_capture(self) -> None:
        """Spawn `pw-record` and read RMS levels from a daemon thread. Must
        never raise -- on any failure the tick loop keeps using the placeholder
        animation instead."""
        self._mic_live = False
        self.mic_level = 0.0
        try:
            self.mic_proc = subprocess.Popen(
                ["pw-record", "--format=s16", "--rate=16000", "--channels=1", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
        except (OSError, ValueError):
            self.mic_proc = None
            return
        try:
            threading.Thread(target=self._mic_reader, args=(self.mic_proc,), daemon=True).start()
        except Exception:
            self._stop_mic_capture()  # no reader -> pipe would fill and wedge pw-record

    def _mic_reader(self, proc) -> None:
        try:
            while True:
                chunk = proc.stdout.read(MIC_CHUNK_BYTES)
                if not chunk:
                    return
                level = rms_level(chunk)
                GLib.idle_add(self._apply_mic_level, level)
        except Exception:
            return  # reader death = silent fallback to the placeholder animation

    def _apply_mic_level(self, level: float) -> bool:
        self._mic_live = True
        self.mic_level = smooth_level(self.mic_level, level)
        return False  # one-shot GLib.idle_add callback

    def _stop_mic_capture(self) -> None:
        proc, self.mic_proc = self.mic_proc, None
        self._mic_live = False
        self.mic_level = 0.0
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=0.5)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass


def main() -> None:
    initial = sys.argv[1] if len(sys.argv) > 1 else "listening"
    app = Pill()
    app.state = initial

    def on_usr1(signum, frame):
        GLib.idle_add(app.set_state, "processing")

    def on_term(signum, frame):
        GLib.idle_add(app._stop_mic_capture)
        GLib.idle_add(app.quit)

    signal.signal(signal.SIGUSR1, on_usr1)
    signal.signal(signal.SIGTERM, on_term)
    app.run(None)


if __name__ == "__main__":
    main()
