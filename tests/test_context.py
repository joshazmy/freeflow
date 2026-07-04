import json
import subprocess

import pytest

from freeflow import context
from freeflow.config import Config


@pytest.fixture(autouse=True)
def reset_detector_cache():
    # active_app() caches which backend last succeeded for the process lifetime;
    # reset it per-test so tests don't depend on execution order.
    context._cached_detector = None
    yield
    context._cached_detector = None


def _run_result(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_active_app_hyprctl(monkeypatch):
    data = json.dumps({"class": "Firefox", "title": "Example - Mozilla Firefox"})

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "hyprctl"
        return _run_result(0, data)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert context.active_app() == ("firefox", "Example - Mozilla Firefox")


def test_active_app_sway_fallback(monkeypatch):
    tree = {
        "nodes": [
            {"focused": False, "app_id": "other"},
            {
                "nodes": [
                    {"focused": True, "app_id": "Alacritty", "name": "term"},
                ]
            },
        ]
    }

    def fake_run(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            return _run_result(1, "")
        if cmd[0] == "swaymsg":
            return _run_result(0, json.dumps(tree))
        raise AssertionError(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert context.active_app() == ("alacritty", "term")


def test_active_app_sway_window_properties_class(monkeypatch):
    tree = {
        "focused": True,
        "window_properties": {"class": "Slack"},
        "name": "general",
    }

    def fake_run(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            return _run_result(1, "")
        return _run_result(0, json.dumps(tree))

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert context.active_app() == ("slack", "general")


def test_active_app_total_failure(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1.0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert context.active_app() == ("", "")


def test_active_app_caches_successful_backend(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[0])
        if cmd[0] == "hyprctl":
            return _run_result(1, "")
        return _run_result(0, json.dumps({"focused": True, "app_id": "kitty", "name": "t"}))

    monkeypatch.setattr(subprocess, "run", fake_run)
    context.active_app()
    calls.clear()
    context.active_app()
    # second call should go straight to the cached swaymsg backend, skipping hyprctl
    assert calls == ["swaymsg"]


def test_active_app_falls_back_once_when_cached_backend_fails(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            return _run_result(1, "")
        return _run_result(0, json.dumps({"focused": True, "app_id": "kitty", "name": "t"}))

    monkeypatch.setattr(subprocess, "run", fake_run)
    context.active_app()  # caches swaymsg

    def fake_run_now_failing(cmd, **kwargs):
        return _run_result(1, "")

    monkeypatch.setattr(subprocess, "run", fake_run_now_failing)
    assert context.active_app() == ("", "")


def test_tone_for_override_wins(monkeypatch):
    cfg = Config(tone_overrides={"discord": "formal"})
    assert context.tone_for("discord", "", cfg) == "formal"


@pytest.mark.parametrize(
    "app_class,title,expected",
    [
        ("thunderbird", "Inbox", "formal"),
        ("evolution", "", "formal"),
        ("betterbird", "", "formal"),
        ("chromium", "Gmail - message", "formal"),
        ("chromium", "Proton Mail - inbox", "formal"),
        ("slack", "#general", "formal"),
        ("teams", "", "formal"),
        ("discord", "#chat", "casual"),
        ("telegram", "", "casual"),
        ("signal", "", "casual"),
        ("whatsapp", "", "casual"),
        ("element", "", "casual"),
        ("code", "main.py", "neutral"),
        ("", "", "neutral"),
    ],
)
def test_tone_for_builtin_categories(app_class, title, expected):
    cfg = Config()
    assert context.tone_for(app_class, title, cfg) == expected
