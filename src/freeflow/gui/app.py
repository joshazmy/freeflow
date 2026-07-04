"""Freeflow settings GUI entry point."""
from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from freeflow.config import load as load_config
from freeflow.gui.state import GuiContext
from freeflow.gui.style import apply_style
from freeflow.gui.window import SettingsWindow

APPLICATION_ID = "io.github.joshazmy.freeflow"


class FreeflowApp(Gtk.Application):
    def __init__(self, config_path: str | None = None, **kwargs):
        super().__init__(application_id=APPLICATION_ID, **kwargs)
        self.config_path = config_path
        self.window = None
        self.connect("activate", self._on_activate)

    def _on_activate(self, app) -> None:
        cfg = load_config(self.config_path)
        apply_style(dark=cfg.dark)
        ctx = GuiContext(cfg=cfg, config_path=self.config_path)
        if self.window is None:
            self.window = SettingsWindow(application=app, ctx=ctx)
        self.window.present()


def main(argv=None) -> int:
    app = FreeflowApp()
    # run with no CLI args: 'freeflow gui' leaves subcommand tokens in sys.argv
    return app.run([sys.argv[0]] if argv is None else argv[:1])
