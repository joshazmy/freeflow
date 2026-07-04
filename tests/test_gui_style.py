"""Tests for freeflow.gui.style — CSS tokens + Gtk CssProvider parsing."""
import pytest


def test_css_contains_required_classes():
    from freeflow.gui.style import CSS

    for cls in (
        ".ff-card",
        ".ff-pill",
        ".ff-pill-active",
        ".ff-serif",
        ".ff-muted",
        ".ff-danger",
        ".ff-mono",
    ):
        assert cls in CSS

    for token in ("#FFFEF0", "#111110", "#E7D4F9"):
        assert token in CSS


def test_css_parses_via_gtk_cssprovider():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    from freeflow.gui.style import CSS

    provider = Gtk.CssProvider()
    errors = []
    try:
        provider.connect("parsing-error", lambda *a: errors.append(a))
    except TypeError:
        pass
    provider.load_from_data(CSS.encode("utf-8"))
    assert errors == []


def test_apply_style_runs_without_error():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        pytest.skip("no display available")

    from freeflow.gui.style import apply_style

    apply_style()  # should not raise
