"""Settings pane registry — contract order, do not reorder (docs/GUI.md)."""
from __future__ import annotations

from freeflow.gui.panes import about, dictionary, general, models, privacy, tone

PANES = [
    ("general", "General", general.build),
    ("dictionary", "Dictionary", dictionary.build),
    ("tone", "Tone & Apps", tone.build),
    ("models", "Models", models.build),
    ("privacy", "Data & Privacy", privacy.build),
    ("about", "About", about.build),
]
