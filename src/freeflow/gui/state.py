"""Shared GUI state: one GuiContext is passed to every settings pane.

No GTK imports here — pure logic, unit-testable headless.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from freeflow.config import Config, save_values
from freeflow.dictionary import Dictionary


@dataclass
class GuiContext:
    cfg: Config
    config_path: Optional[str] = None       # None -> default ~/.config/freeflow/config.toml
    restart_needed: bool = False
    on_restart_needed: Optional[Callable[[], None]] = None
    _dictionary: Optional[Dictionary] = field(default=None, repr=False)

    def save(self, **updates) -> None:
        """Persist updates to the config file, mirror them onto cfg, flag restart."""
        save_values(updates, self.config_path)
        for k, v in updates.items():
            setattr(self.cfg, k, v)
        self.restart_needed = True
        if self.on_restart_needed:
            self.on_restart_needed()

    @property
    def dictionary(self) -> Dictionary:
        if self._dictionary is None:
            self._dictionary = Dictionary(self.cfg.dictionary_path)
        return self._dictionary
