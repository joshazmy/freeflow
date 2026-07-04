# Changelog

## 0.3.1 — 2026-07-04

- Switches now really match the theme everywhere — desktop themes/rices that ship their own
  GTK styling can no longer repaint Freeflow's controls.
- Settings panes scroll instead of cutting controls off when the window is tiled small.
- A dead network connection can no longer freeze a model download or pull forever — it now
  times out and re-enables the buttons with an error message.

## 0.3.0 — 2026-07-04

- **Dark mode** — warm dark theme with a switch in General; applies instantly, no restart.
- **Themed switches** — all toggle switches now match the Freeflow look (no more stock blue).
- **New wordmark font** — the "Freeflow" sidebar title is now an italic serif.
- **Downloadable models** — picking a speech model you don't have shows a Download button with
  a progress bar (from whisper.cpp's official model repo). Same for the cleanup model: if it
  isn't in your local Ollama, a Pull button fetches it.
- **Cleanup explained** — the Models pane now says in plain English what AI cleanup does and
  that dictation never blocks on it.
- **Tones explained** — Tone & Apps shows what Formal/Neutral/Casual mean with a real
  before/after example for each.
- **Friendlier onboarding** — a new first step explains how local speech-to-text works
  (no cloud, no account, nothing leaves your computer).
- **Easy install/uninstall** — install.sh now shows its full plan and asks before touching
  anything; new uninstall.sh removes everything it installed (with --dry-run, and it asks
  before deleting your models, config, or history).

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
