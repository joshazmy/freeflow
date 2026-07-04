"""Syntax + safety checks for install.sh / uninstall.sh (no real install run)."""
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALL = REPO / "install.sh"
UNINSTALL = REPO / "uninstall.sh"


def test_install_sh_syntax_ok():
    r = subprocess.run(["bash", "-n", str(INSTALL)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_uninstall_sh_syntax_ok():
    r = subprocess.run(["bash", "-n", str(UNINSTALL)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_uninstall_never_references_whisper_dictation():
    # The OLD unrelated daemon lives at ~/.local/share/whisper-dictation — never touch it.
    assert "whisper-dictation" not in UNINSTALL.read_text()


def test_uninstall_dry_run_deletes_nothing(tmp_path):
    home = tmp_path / "home"
    unit = home / ".config/systemd/user/freeflow.service"
    unit.parent.mkdir(parents=True)
    unit.write_text("[Unit]\n")
    model = home / ".local/share/freeflow/models/ggml-small.bin"
    model.parent.mkdir(parents=True)
    model.write_text("fake model")
    config = home / ".config/freeflow/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text("x = 1\n")

    env = {**os.environ, "HOME": str(home)}
    r = subprocess.run(
        ["bash", str(UNINSTALL), "--dry-run"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout + r.stderr
    assert "freeflow.service" in out           # mentions the unit
    assert "ggml-small.bin" in out             # mentions the model path
    # dry-run deletes NOTHING
    assert unit.exists()
    assert model.exists()
    assert config.exists()
