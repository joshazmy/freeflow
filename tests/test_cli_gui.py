"""Tests for the gui/onboarding/tray CLI subcommands. Fake modules are injected
into sys.modules so these run without GTK/ksni installed."""
import sys
import types

from freeflow.cli import build_parser


def test_parser_accepts_gui_subcommands():
    for name in ("gui", "onboarding", "tray"):
        args = build_parser().parse_args([name])
        assert args.command == name
        assert callable(args.func)


def _fake_module(monkeypatch, dotted_path, retval=0):
    calls = []

    def fake_main(*a, **kw):
        calls.append((a, kw))
        return retval

    mod = types.ModuleType(dotted_path)
    mod.main = fake_main
    monkeypatch.setitem(sys.modules, dotted_path, mod)
    return calls


def test_cmd_gui_calls_app_main(monkeypatch):
    calls = _fake_module(monkeypatch, "freeflow.gui.app", retval=0)
    args = build_parser().parse_args(["gui"])
    assert args.func(args) == 0
    assert calls


def test_cmd_onboarding_calls_onboarding_main(monkeypatch):
    calls = _fake_module(monkeypatch, "freeflow.gui.onboarding", retval=0)
    args = build_parser().parse_args(["onboarding"])
    assert args.func(args) == 0
    assert calls


def test_cmd_tray_calls_tray_main(monkeypatch):
    calls = _fake_module(monkeypatch, "freeflow.gui.tray", retval=1)
    args = build_parser().parse_args(["tray"])
    assert args.func(args) == 1
    assert calls
