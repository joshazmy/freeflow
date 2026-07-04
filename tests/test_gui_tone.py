"""Tests for gui/panes/tone.py."""
import pytest

from freeflow.config import load, save_default
from freeflow.gui.state import GuiContext
from freeflow.gui.panes import tone


def _ctx(tmp_path, tone_overrides=None):
    cfg_path = tmp_path / "config.toml"
    save_default(str(cfg_path))
    cfg = load(str(cfg_path))
    if tone_overrides:
        cfg.tone_overrides = tone_overrides
    return GuiContext(cfg=cfg, config_path=str(cfg_path))


# ---- headless logic ----

def test_tone_categories_keys():
    keys = [k for _, k in tone.TONE_CATEGORIES]
    assert keys == ["_email", "_work_chat", "_personal_chat", "_default"]


def test_category_tone_defaults_match_context_builtins(tmp_path):
    ctx = _ctx(tmp_path)
    assert tone.category_tone(ctx.cfg, "_email") == "formal"
    assert tone.category_tone(ctx.cfg, "_work_chat") == "formal"
    assert tone.category_tone(ctx.cfg, "_personal_chat") == "casual"
    assert tone.category_tone(ctx.cfg, "_default") == "neutral"


def test_category_tone_reads_override(tmp_path):
    ctx = _ctx(tmp_path, tone_overrides={"_email": "casual"})
    assert tone.category_tone(ctx.cfg, "_email") == "casual"


def test_per_app_overrides_excludes_category_keys(tmp_path):
    ctx = _ctx(tmp_path, tone_overrides={
        "_email": "formal", "discord": "casual", "thunderbird": "formal",
    })
    assert tone.per_app_overrides(ctx.cfg) == {"discord": "casual", "thunderbird": "formal"}


# ---- widget tests ----

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check():
    pytest.skip("no display available for GTK widget tests", allow_module_level=True)


def _find(widget, name):
    if widget.get_name() == name:
        return widget
    child = widget.get_first_child()
    while child is not None:
        found = _find(child, name)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


def test_build_returns_widget(tmp_path):
    ctx = _ctx(tmp_path)
    root = tone.build(ctx)
    assert isinstance(root, Gtk.Widget)


def test_category_pill_click_persists(tmp_path):
    ctx = _ctx(tmp_path)
    root = tone.build(ctx)
    btn = _find(root, "tone-_email-casual")
    assert btn is not None
    btn.emit("clicked")
    assert load(ctx.config_path).tone_overrides.get("_email") == "casual"


def test_per_app_row_rendered(tmp_path):
    ctx = _ctx(tmp_path, tone_overrides={"discord": "casual"})
    root = tone.build(ctx)
    assert _find(root, "tone-discord-casual") is not None


def test_add_app_persists(tmp_path):
    ctx = _ctx(tmp_path)
    root = tone.build(ctx)
    entry = _find(root, "tone-add-app-entry")
    entry.set_text("slack")
    add_btn = _find(root, "tone-add-app-button")
    add_btn.emit("clicked")
    assert load(ctx.config_path).tone_overrides.get("slack") == "neutral"
