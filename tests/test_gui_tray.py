"""Tests for freeflow.gui.tray (AppIndicator3 via gi, GTK3).

GTK3 cannot load into a process that already loaded GTK4 (the other GUI tests),
so the indicator construction is exercised in a subprocess; the in-process
tests cover the degrade path and the menu-action helpers."""
import os
import subprocess
import sys

from freeflow.gui import tray


def test_main_returns_1_and_prints_hint_without_appindicator(capsys, monkeypatch):
    monkeypatch.setattr(tray, "_load_appindicator", lambda: None)
    ret = tray.main()
    out = capsys.readouterr().out
    assert ret == 1
    assert "appindicator" in out.lower()


def test_indicator_builds_in_gtk3_subprocess():
    """Real AppIndicator3 construction (menu labels included), own process."""
    code = (
        "from freeflow.gui import tray\n"
        "mods = tray._load_appindicator()\n"
        "import sys\n"
        "if mods is None: print('SKIP'); sys.exit(0)\n"
        "ind, labels = tray._build_indicator(*mods)\n"
        "print('|'.join(labels))\n"
    )
    env = dict(os.environ, PYTHONPATH="src")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env,
                       text=True, timeout=15, cwd=os.path.dirname(os.path.dirname(__file__)))
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    if out == "SKIP":
        import pytest
        pytest.skip("AppIndicator3 typelib not available")
    assert out.startswith("Open Settings|")
    assert "dictation" in out
    assert out.endswith("Quit tray")


def test_open_settings_launches_gui(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append(args))
    tray.open_settings()
    assert calls == [[sys.executable, "-m", "freeflow.cli", "gui"]]


def test_open_settings_swallows_errors(monkeypatch):
    def boom(*a, **kw):
        raise OSError("no freeflow binary")
    monkeypatch.setattr(subprocess, "Popen", boom)
    tray.open_settings()  # must not raise


def test_is_active_true(monkeypatch):
    def fake_run(args, **kw):
        assert args == ["systemctl", "--user", "is-active", "freeflow"]
        return subprocess.CompletedProcess(args, 0, stdout="active\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert tray.dictation_active() is True


def test_is_active_false_on_error(monkeypatch):
    def boom(*a, **kw):
        raise OSError("no systemctl")
    monkeypatch.setattr(subprocess, "run", boom)
    assert tray.dictation_active() is False


def test_toggle_dictation_pauses_when_active(monkeypatch):
    calls = []
    monkeypatch.setattr(tray, "dictation_active", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append(args))
    tray.toggle_dictation()
    assert calls == [["systemctl", "--user", "stop", "freeflow"]]


def test_toggle_dictation_resumes_when_inactive(monkeypatch):
    calls = []
    monkeypatch.setattr(tray, "dictation_active", lambda: False)
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append(args))
    tray.toggle_dictation()
    assert calls == [["systemctl", "--user", "start", "freeflow"]]


def test_toggle_dictation_swallows_errors(monkeypatch):
    monkeypatch.setattr(tray, "dictation_active", lambda: True)
    def boom(*a, **kw):
        raise OSError("no systemctl")
    monkeypatch.setattr(subprocess, "run", boom)
    tray.toggle_dictation()  # must not raise


def test_toggle_label():
    assert tray.toggle_label(True) == "Pause dictation"
    assert tray.toggle_label(False) == "Resume dictation"
