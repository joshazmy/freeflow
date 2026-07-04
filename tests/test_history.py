"""Dictation history store: local JSONL, capped, clearable."""
import json

from freeflow.history import History


def test_append_and_read(tmp_path):
    h = History(str(tmp_path / "history.jsonl"))
    h.append(raw="um hello", cleaned="Hello.", app="kitty", tone="neutral", ts=1000.0)
    h.append(raw="uh test", cleaned="Test.", app="discord", tone="casual", ts=1001.0)
    entries = h.read_all()
    assert len(entries) == 2
    assert entries[0]["cleaned"] == "Test."      # newest first
    assert entries[1]["raw"] == "um hello"
    assert entries[0]["app"] == "discord"


def test_cap_keeps_newest(tmp_path):
    h = History(str(tmp_path / "h.jsonl"), cap=5)
    for i in range(9):
        h.append(raw=f"r{i}", cleaned=f"c{i}", app="a", tone="neutral", ts=float(i))
    entries = h.read_all()
    assert len(entries) == 5
    assert entries[0]["cleaned"] == "c8" and entries[-1]["cleaned"] == "c4"


def test_clear(tmp_path):
    p = tmp_path / "h.jsonl"
    h = History(str(p))
    h.append(raw="x", cleaned="X", app="a", tone="neutral", ts=1.0)
    h.clear()
    assert h.read_all() == []


def test_corrupt_lines_skipped(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text('{"raw":"ok","cleaned":"Ok.","app":"a","tone":"neutral","ts":1.0}\nNOT JSON\n')
    assert len(History(str(p)).read_all()) == 1


def test_append_never_raises_on_bad_dir(tmp_path):
    h = History(str(tmp_path / "no" / "such" / "deep" / "h.jsonl"))
    h.append(raw="x", cleaned="X", app="a", tone="neutral", ts=1.0)  # creates dirs
    assert len(h.read_all()) == 1
