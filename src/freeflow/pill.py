"""Wispr-Flow-style pill overlay: python -m freeflow.pill [listening|processing].

GTK4 + gtk4-layer-shell. SIGUSR1 -> processing state, SIGTERM -> exit.
Exits with status 3 if gi / layer-shell setup is unavailable (caller falls back to notify).
"""
import math
import random
import signal
import sys

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import GLib, Gtk, Gtk4LayerShell
except Exception:
    sys.exit(3)

WIDTH, HEIGHT = 72, 26
BAR_COUNT = 5
DOT_COUNT = 3


class Pill(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.freeflow.pill")
        self.state = "listening"
        self.bar_heights = [6.0] * BAR_COUNT
        self.dot_phase = 0.0
        self.window = None

    def do_activate(self):
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

        GLib.timeout_add(80, self._tick)

    def _tick(self) -> bool:
        if self.state == "listening":
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
        self.state = state
        if self.area is not None:
            self.area.queue_draw()


def main() -> None:
    initial = sys.argv[1] if len(sys.argv) > 1 else "listening"
    app = Pill()
    app.state = initial

    def on_usr1(signum, frame):
        GLib.idle_add(app.set_state, "processing")

    def on_term(signum, frame):
        GLib.idle_add(app.quit)

    signal.signal(signal.SIGUSR1, on_usr1)
    signal.signal(signal.SIGTERM, on_term)
    app.run(None)


if __name__ == "__main__":
    main()
