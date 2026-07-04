import sys
import types

import pytest

from freeflow import __version__, cli


def test_version(capsys):
    rc = cli.cmd_version(None)
    out = capsys.readouterr().out.strip()
    assert out == __version__
    assert rc == 0


def test_main_version(capsys):
    with pytest.raises(SystemExit) as exc:
        sys.argv = ["freeflow", "version"]
        cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out == __version__


def test_config_print(tmp_path, monkeypatch, capsys):
    args = cli.build_parser().parse_args(["config"])
    rc = cli.cmd_config(args)
    out = capsys.readouterr().out
    assert "whisper_bin" in out
    assert rc == 0


def test_config_init(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CONFIG_DIR", tmp_path, raising=False)
    from freeflow import config as config_mod
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    args = cli.build_parser().parse_args(["config", "--init"])
    rc = cli.cmd_config(args)
    assert rc == 0
    assert (tmp_path / "config.toml").exists()


def test_dictionary_add_wires_to_dictionary_class(monkeypatch):
    calls = {}

    class FakeDictionary:
        def __init__(self, path):
            calls["path"] = path

        def add(self, entry):
            calls["add"] = entry

    fake_mod = types.ModuleType("freeflow.dictionary")
    fake_mod.Dictionary = FakeDictionary
    monkeypatch.setitem(sys.modules, "freeflow.dictionary", fake_mod)

    args = cli.build_parser().parse_args(["dictionary", "add", "Hyprland"])
    rc = cli.cmd_dictionary(args)
    assert rc == 0
    assert calls["add"] == "Hyprland"


def test_dictionary_list_wires_to_dictionary_class(monkeypatch, capsys):
    class FakeDictionary:
        def __init__(self, path):
            pass

        @property
        def words(self):
            return ["Hyprland", "Wispr"]

    fake_mod = types.ModuleType("freeflow.dictionary")
    fake_mod.Dictionary = FakeDictionary
    monkeypatch.setitem(sys.modules, "freeflow.dictionary", fake_mod)

    args = cli.build_parser().parse_args(["dictionary", "list"])
    rc = cli.cmd_dictionary(args)
    out = capsys.readouterr().out
    assert "Hyprland" in out and "Wispr" in out
    assert rc == 0


def test_status_reports_failure_when_nothing_reachable(monkeypatch):
    monkeypatch.setattr(cli, "_http_reachable", lambda *a, **k: False)
    monkeypatch.setattr(cli, "_ollama_has_model", lambda *a, **k: False)
    monkeypatch.setattr(cli, "_systemd_active", lambda *a, **k: False)
    monkeypatch.setattr("os.path.exists", lambda p: False)
    rc = cli.cmd_status(None)
    assert rc == 1


def test_status_ok_when_binaries_present(monkeypatch, tmp_path):
    whisper_bin = tmp_path / "whisper-cli"
    whisper_bin.write_text("x")
    model = tmp_path / "model.bin"
    model.write_text("x")

    from freeflow.config import Config
    fake_cfg = Config(whisper_bin=str(whisper_bin), model_path=str(model), server="")
    monkeypatch.setattr(cli, "load", lambda *a, **k: fake_cfg)
    monkeypatch.setattr(cli, "_http_reachable", lambda *a, **k: False)  # ollama down is a warning
    monkeypatch.setattr(cli, "_systemd_active", lambda *a, **k: False)

    socket = tmp_path / "ydotoold.socket"
    socket.write_text("x")
    monkeypatch.setenv("YDOTOOL_SOCKET", str(socket))

    rc = cli.cmd_status(None)
    assert rc == 0
