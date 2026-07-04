"""Tests for freeflow.gui.style — build_css(dark) tokens + apply_style re-callability."""
import pytest


def test_build_css_light_matches_existing_tokens():
    from freeflow.gui.style import build_css

    css = build_css(False)
    for cls in (
        ".ff-card",
        ".ff-pill",
        ".ff-pill-active",
        ".ff-serif",
        ".ff-muted",
        ".ff-danger",
        ".ff-mono",
        "switch",
        "switch slider",
        "switch:checked",
    ):
        assert cls in css

    for token in ("#FFFEF0", "#111110", "#E7D4F9"):
        assert token in css

    # light window background is cream, not the dark bg token
    assert "#171613" not in css


def test_build_css_dark_tokens():
    from freeflow.gui.style import build_css

    css = build_css(True)
    for token in ("#171613", "#211F1B", "#FFFEF0", "#E7D4F9", "#E08080"):
        assert token in css

    # window in dark mode must not use the light cream background
    window_rule = css.split("}", 1)[0]
    assert "background-color: #171613" in window_rule
    assert "background-color: #FFFEF0" not in window_rule
    assert "color: #FFFEF0" in window_rule  # cream text on the dark window
    assert "switch" in css and "switch:checked" in css


def test_build_css_is_pure_and_headless():
    from freeflow.gui.style import build_css

    # calling twice with the same arg gives identical output, no side effects
    assert build_css(False) == build_css(False)
    assert build_css(True) != build_css(False)


def test_css_parses_via_gtk_cssprovider():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    from freeflow.gui.style import build_css

    for dark in (False, True):
        provider = Gtk.CssProvider()
        errors = []
        try:
            provider.connect("parsing-error", lambda *a: errors.append(a))
        except TypeError:
            pass
        provider.load_from_data(build_css(dark).encode("utf-8"))
        assert errors == []


def test_apply_style_runs_without_error():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    from freeflow.gui.style import apply_style

    apply_style()  # should not raise
    apply_style(dark=True)  # should not raise


def test_apply_style_is_recallable_and_does_not_stack_providers():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    import freeflow.gui.style as style_mod

    style_mod.apply_style(dark=False)
    first_provider = style_mod._current_provider
    assert first_provider is not None

    style_mod.apply_style(dark=True)
    second_provider = style_mod._current_provider
    assert second_provider is not None
    assert second_provider is not first_provider
