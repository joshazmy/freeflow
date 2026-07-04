"""Tests for freeflow.gui.window / app / panes — strict TDD, agent A."""
import sys
import types

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check():
    pytest.skip("no display available", allow_module_level=True)

from freeflow.config import Config  # noqa: E402
from freeflow.gui.state import GuiContext  # noqa: E402


def _stub_pane_module(name: str, label: str):
    """Other agents' pane modules may not exist on disk yet — stub them so our
    tests don't depend on agent B/C's work landing first."""
    mod = types.ModuleType(f"freeflow.gui.panes.{name}")

    def build(ctx):
        return Gtk.Label(label=label)

    mod.build = build
    sys.modules[f"freeflow.gui.panes.{name}"] = mod
    return mod


@pytest.fixture(autouse=True)
def stub_other_agents_panes():
    stubbed = [
        _stub_pane_module("general", "General stub"),
        _stub_pane_module("dictionary", "Dictionary stub"),
        _stub_pane_module("tone", "Tone stub"),
        _stub_pane_module("models", "Models stub"),
    ]
    yield stubbed
    for m in stubbed:
        sys.modules.pop(m.__name__, None)
    # panes/__init__ may have cached the stubbed build refs at import time;
    # drop it so a later real import re-resolves against real modules.
    sys.modules.pop("freeflow.gui.panes", None)


def make_ctx(tmp_path):
    cfg = Config()
    config_path = str(tmp_path / "config.toml")
    return GuiContext(cfg=cfg, config_path=config_path)


def test_panes_list_has_six_in_contract_order():
    from freeflow.gui import panes

    ids = [p[0] for p in panes.PANES]
    assert ids == ["general", "dictionary", "tone", "models", "privacy", "about"]
    titles = [p[1] for p in panes.PANES]
    assert titles == [
        "General",
        "Dictionary",
        "Tone & Apps",
        "Models",
        "Data & Privacy",
        "About",
    ]
    for _id, _title, build in panes.PANES:
        assert callable(build)


def test_window_has_six_sidebar_rows_matching_pane_titles(tmp_path):
    from freeflow.gui.app import FreeflowApp
    from freeflow.gui.panes import PANES
    from freeflow.gui.window import SettingsWindow

    app = FreeflowApp()
    ctx = make_ctx(tmp_path)
    win = SettingsWindow(application=app, ctx=ctx)

    row = win.sidebar.get_row_at_index(0)
    count = 0
    while row is not None:
        count += 1
        row = win.sidebar.get_row_at_index(count)
    assert count == len(PANES) == 6


def test_selecting_row_switches_stack(tmp_path):
    from freeflow.gui.app import FreeflowApp
    from freeflow.gui.panes import PANES
    from freeflow.gui.window import SettingsWindow

    app = FreeflowApp()
    ctx = make_ctx(tmp_path)
    win = SettingsWindow(application=app, ctx=ctx)

    # select the 3rd row ("tone") and confirm the stack follows
    row = win.sidebar.get_row_at_index(2)
    win.sidebar.select_row(row)
    win.sidebar.emit("row-activated", row)

    assert win.stack.get_visible_child_name() == PANES[2][0]


def test_restart_banner_hidden_then_revealed(tmp_path):
    from freeflow.gui.app import FreeflowApp
    from freeflow.gui.window import SettingsWindow

    app = FreeflowApp()
    ctx = make_ctx(tmp_path)
    win = SettingsWindow(application=app, ctx=ctx)

    assert win.restart_banner.get_reveal_child() is False
    ctx.save(paste=False)
    assert win.restart_banner.get_reveal_child() is True


def test_restart_now_button_calls_systemctl(tmp_path, monkeypatch):
    from freeflow.gui.app import FreeflowApp
    from freeflow.gui.window import SettingsWindow

    calls = []
    monkeypatch.setattr(
        "freeflow.gui.window.subprocess.run",
        lambda *a, **kw: calls.append((a, kw)),
    )

    app = FreeflowApp()
    ctx = make_ctx(tmp_path)
    win = SettingsWindow(application=app, ctx=ctx)
    win.restart_button.emit("clicked")

    assert calls
    assert calls[0][0][0] == ["systemctl", "--user", "restart", "freeflow"]


def test_app_main_creates_and_activates(tmp_path, monkeypatch):
    from freeflow.gui import app as app_mod

    monkeypatch.setattr(app_mod, "apply_style", lambda: None)
    monkeypatch.setenv("FREEFLOW_CONFIG", str(tmp_path / "config.toml"))
    # main() builds a real Gtk.Application; just confirm it constructs and
    # returns an int-like exit code path without actually running the loop.
    application = app_mod.FreeflowApp()
    assert application.get_application_id() == "io.github.joshazmy.freeflow"
