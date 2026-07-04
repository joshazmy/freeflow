"""User dictionary: forced spellings applied to transcripts.

File format: one entry per line, "wrong->right" or plain "CanonicalWord".
Lines starting with # are comments/ignored.
"""
from __future__ import annotations

import os
import re
import tempfile


class Dictionary:
    def __init__(self, path: str):
        self.path = path
        self._pairs: dict[str, str] = {}   # lowercase wrong -> right (includes plain-word case-folds)
        self._canonical: list[str] = []    # right-hand sides / plain words, in file order
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                self._add_line(line)

    def _add_line(self, line: str) -> None:
        if "->" in line:
            wrong, right = line.split("->", 1)
            wrong, right = wrong.strip(), right.strip()
        else:
            wrong, right = line, line.strip()
        if not right:
            return
        self._pairs[wrong.lower()] = right
        self._canonical.append(right)

    @property
    def words(self) -> list[str]:
        return list(self._canonical)

    def add(self, entry: str) -> None:
        entry = entry.strip()
        if not entry:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._add_line(entry)
        self._rewrite()

    def remove(self, entry: str) -> None:
        entry = entry.strip()
        if "->" in entry:
            wrong = entry.split("->", 1)[0].strip().lower()
        else:
            wrong = entry.lower()
        right = self._pairs.pop(wrong, None)
        if right is not None and right in self._canonical:
            self._canonical.remove(right)
        self._rewrite()

    def _rewrite(self) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        lines = []
        seen_right = set()
        for wrong, right in self._pairs.items():
            if wrong == right.lower():
                if right not in seen_right:
                    lines.append(right)
                    seen_right.add(right)
            else:
                lines.append(f"{wrong}->{right}")
        content = "\n".join(lines) + ("\n" if lines else "")

        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".dictionary-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, self.path)
        except BaseException:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    def apply(self, text: str) -> str:
        if not self._pairs:
            return text

        def repl(m: re.Match) -> str:
            word = m.group(0)
            right = self._pairs.get(word.lower())
            return right if right is not None else word

        for wrong in self._pairs:
            pattern = r"\b" + re.escape(wrong) + r"\b"
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text
