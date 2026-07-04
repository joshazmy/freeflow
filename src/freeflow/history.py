"""Dictation history: local JSONL, newest-last on disk, capped.

100% local (Data & Privacy pane documents it; `history = false` disables).
Appends must never break a dictation -- callers rely on best-effort semantics.
"""
from __future__ import annotations

import json
import os
import tempfile

DEFAULT_PATH = os.path.expanduser("~/.local/share/freeflow/history.jsonl")
DEFAULT_CAP = 200


class History:
    def __init__(self, path: str = DEFAULT_PATH, cap: int = DEFAULT_CAP):
        self.path = path
        self.cap = cap

    def append(self, *, raw: str, cleaned: str, app: str, tone: str, ts: float) -> None:
        entry = {"ts": ts, "raw": raw, "cleaned": cleaned, "app": app, "tone": tone}
        lines = self._lines()
        lines.append(json.dumps(entry, ensure_ascii=False))
        self._rewrite(lines[-self.cap:])

    def read_all(self) -> list[dict]:
        """Entries newest-first."""
        out = []
        for line in self._lines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        out.reverse()
        return out

    def clear(self) -> None:
        self._rewrite([])

    def _lines(self) -> list[str]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return [l for l in (line.strip() for line in f) if l]
        except OSError:
            return []

    def _rewrite(self, lines: list[str]) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        content = "\n".join(lines) + ("\n" if lines else "")
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".history-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
