"""Dictionary pane: plain logic tested headless, widget build tested via GTK if available."""
import pytest

from freeflow.config import load, save_default
from freeflow.gui.panes import dictionary
from freeflow.gui.state import GuiContext


def _ctx(tmp_path):
    cfg_path = tmp_path / "config.toml"
    save_default(str(cfg_path))
    cfg = load(str(cfg_path))
    cfg.dictionary_path = str(tmp_path / "dictionary.txt")
    return GuiContext(cfg=cfg, config_path=str(cfg_path))


def test_entries_for_display_plain_word(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.dictionary.add("Hyprland")
    entries = dictionary.entries_for_display(ctx.dictionary)
    assert entries == [("Hyprland", "Hyprland")]


def test_entries_for_display_correction(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.dictionary.add("hyperland->Hyprland")
    entries = dictionary.entries_for_display(ctx.dictionary)
    assert entries == [("hyperland → Hyprland", "hyperland")]


def test_entries_for_display_mixed_order(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.dictionary.add("Hyprland")
    ctx.dictionary.add("9Router")
    ctx.dictionary.add("hyperland->Hyprland")
    entries = dictionary.entries_for_display(ctx.dictionary)
    assert entries == [
        ("Hyprland", "Hyprland"),
        ("9Router", "9Router"),
        ("hyperland → Hyprland", "hyperland"),
    ]


def test_build_returns_widget(tmp_path):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    ctx = _ctx(tmp_path)
    ctx.dictionary.add("Hyprland")
    ctx.dictionary.add("hyperland->Hyprland")

    widget = dictionary.build(ctx)
    assert isinstance(widget, Gtk.Widget)


def test_build_add_and_remove_roundtrip(tmp_path):
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    ctx = _ctx(tmp_path)
    dictionary.build(ctx)

    ctx.dictionary.add("word->Word")
    assert ctx.dictionary.words == ["Word"]

    ctx.dictionary.remove("word")
    assert ctx.dictionary.words == []
