# Changelog

## 0.2.0 — 2026-07-04

- **Dictation history**: every dictation is now kept locally (last 200, `~/.local/share/freeflow/history.jsonl`).
  New **History** pane in Settings — click an entry to copy the cleaned text, expand ⌄ to see the raw
  transcript. Turn it off with `history = false` in config; wipe it with the **Clear history** button
  in Data & Privacy. Never leaves your machine.
- **The pill now shows your real mic level** while listening — bars move with your voice, so a muted
  or silent mic is visible instantly. Falls back to the old animation if audio capture isn't available.
- **Quick tone switch in the tray**: right-click the tray icon → Default tone → Neutral / Formal / Casual.

## 0.1.0 — 2026-07-04

- First release: hold-to-talk local dictation (whisper.cpp) with local AI cleanup (Ollama) — filler
  removal, Backtrack self-correction, spoken punctuation, lists, per-app tone, personal dictionary.
- GTK4 settings window, 5-step onboarding, system tray, animated pill overlay.
- One-command installer with GPU probe and automatic model pick. 100% local, no accounts, no telemetry.
