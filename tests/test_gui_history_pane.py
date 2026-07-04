"""History pane: plain logic tested headless, widget build tested via GTK if available."""
import time

import pytest

from freeflow.gui.panes import history as history_pane
from freeflow.gui.state import GuiContext
from freeflow.config import Config
from freeflow.history import History


def _ctx(tmp_path):
    cfg = Config()
    return GuiContext(cfg=cfg, config_path=str(tmp_path / "config.toml"))


def _entry(ts=1000.0, raw="um send the file", cleaned="Send the file.", app="Terminal", tone="neutral"):
    return {"ts": ts, "raw": raw, "cleaned": cleaned, "app": app, "tone": tone}


# ---- plain logic ----------------------------------------------------------


def test_format_caption():
    ts = 1_700_000_000.0
    entry = _entry(ts=ts, app="Slack", tone="casual")
    hhmm = time.strftime("%H:%M", time.localtime(ts))
    assert history_pane.format_caption(entry) == f"Slack · casual · {hhmm}"


def test_display_entries_newest_first_and_capped():
    class FakeHistory:
        def read_all(self):
            return [_entry(ts=float(i)) for i in range(60, 0, -1)]

    entries = history_pane.display_entries(FakeHistory(), limit=50)
    assert len(entries) == 50
    assert entries[0]["ts"] == 60
    assert entries[-1]["ts"] == 11


def test_display_entries_respects_default_limit():
    class FakeHistory:
        def read_all(self):
            return [_entry(ts=float(i)) for i in range(3)]

    entries = history_pane.display_entries(FakeHistory())
    assert len(entries) == 3


# ---- widget build -----------------------------------------------------


def test_build_returns_widget_empty_state(tmp_path, monkeypatch):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    class FakeHistory:
        def read_all(self):
            return []

    monkeypatch.setattr(history_pane, "HISTORY_FACTORY", lambda: FakeHistory())

    ctx = _ctx(tmp_path)
    widget = history_pane.build(ctx)
    assert isinstance(widget, Gtk.Widget)


def test_build_lists_entries(tmp_path, monkeypatch):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    real = History(path=str(tmp_path / "history.jsonl"))
    real.append(raw="um send it", cleaned="Send it.", app="Terminal", tone="neutral", ts=1000.0)
    real.append(raw="uh hello there", cleaned="Hello there.", app="Slack", tone="casual", ts=2000.0)

    monkeypatch.setattr(history_pane, "HISTORY_FACTORY", lambda: History(path=real.path))

    ctx = _ctx(tmp_path)
    widget = history_pane.build(ctx)
    assert isinstance(widget, Gtk.Widget)


def test_build_refresh_reloads_after_clear(tmp_path, monkeypatch):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    real = History(path=str(tmp_path / "history.jsonl"))
    real.append(raw="raw one", cleaned="Clean one.", app="Terminal", tone="neutral", ts=1000.0)

    monkeypatch.setattr(history_pane, "HISTORY_FACTORY", lambda: History(path=real.path))

    ctx = _ctx(tmp_path)
    widget = history_pane.build(ctx)
    assert isinstance(widget, Gtk.Widget)

    real.clear()
    # refresh button must exist and be clickable without raising
    assert widget._ff_refresh_button is not None
    widget._ff_refresh_button.emit("clicked")


# --- privacy pane: Clear history (two-click confirm) ---

def test_privacy_clear_history_requires_two_clicks(tmp_path, monkeypatch):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("no display")
    from freeflow.gui.panes import privacy
    from freeflow.history import History
    from freeflow.config import load, save_default
    from freeflow.gui.state import GuiContext

    hpath = tmp_path / "h.jsonl"
    h = History(str(hpath))
    h.append(raw="x", cleaned="X", app="a", tone="neutral", ts=1.0)
    monkeypatch.setattr(privacy, "HISTORY_FACTORY", lambda: History(str(hpath)))

    cfg_path = tmp_path / "config.toml"
    save_default(str(cfg_path))
    ctx = GuiContext(cfg=load(str(cfg_path)), config_path=str(cfg_path))
    root = privacy.build(ctx)

    # find the clear button
    def find_button(w, label_part):
        if isinstance(w, Gtk.Button) and label_part in (w.get_label() or ""):
            return w
        child = w.get_first_child()
        while child:
            found = find_button(child, label_part)
            if found:
                return found
            child = child.get_next_sibling()
        return None

    btn = find_button(root, "Clear history")
    assert btn is not None
    btn.emit("clicked")                       # first click: arm only
    assert len(History(str(hpath)).read_all()) == 1
    assert "Really" in btn.get_label()
    btn.emit("clicked")                       # second click: clears
    assert History(str(hpath)).read_all() == []
