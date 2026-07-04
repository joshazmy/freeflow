# GUI Round 3 — pinned contract

Branch: `gui-round3`. Three agents, disjoint file ownership, zero shared edits.
Rules from `docs/GUI.md` still apply (TDD, GTK test skips, GLib.idle_add from threads,
run ONLY your own test files). One rule change:

> **Network rule (round 3):** user-initiated model downloads ARE allowed:
> whisper ggml from `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-<name>.bin`
> and Ollama pulls via the localhost daemon API. Everything else stays localhost-only.

## Ownership

| Agent | Files (src) | Test files |
|---|---|---|
| A (theme) | `gui/style.py`, `gui/window.py`, `gui/app.py`, `config.py` | `tests/test_gui_style.py`, `tests/test_config.py` |
| B (models) | `gui/panes/models.py` | `tests/test_gui_models.py` |
| C (panes) | `gui/panes/general.py`, `gui/panes/tone.py`, `gui/state.py` | `tests/test_gui_general.py`, `tests/test_gui_tone.py`, `tests/test_gui_state.py` |
| D (onboard/install) | `gui/onboarding.py`, `install.sh`, `uninstall.sh` (new), `README.md` | `tests/test_gui_onboarding.py`, `tests/test_install_scripts.py` (new) |

## Shared interfaces (code against these; don't wait for the other agent)

- `freeflow.config.Config` gains `dark: bool = False` (TOML key `dark`) — agent A.
- `freeflow.gui.style.apply_style(dark: bool = False)` — RE-CALLABLE at runtime to live-switch
  theme: module keeps the last `Gtk.CssProvider`, removes it from the display before adding the
  new one. `build_css(dark: bool) -> str` is a pure function (headless-testable). — agent A.
- `GuiContext.save(_restart: bool = True, **updates)` — `_restart=False` persists + mirrors onto
  cfg but does NOT flag/show the restart banner (used by dark mode; theme applies live). — agent C.

## Palette (agent A)

Light stays exactly as-is. Dark tokens:
`bg #171613`, `card #211F1B`, `text = CREAM #FFFEF0`, accent = LAVENDER `#E7D4F9` with **INK text
on active pills/selected rows**, muted = cream at 60%, danger `#E08080`, mono chip = lavender bg +
ink text (unchanged), card border/shadow use cream at low alpha instead of ink.

Also in agent A's scope:

1. **Switches must match the theme** (both themes): style `switch`, `switch slider`,
   `switch:checked` — pill shape (radius 999px), 1px border (ink in light / cream-alpha in dark),
   cream/card bg unchecked, LAVENDER bg checked, slider = round INK knob in light / CREAM knob in
   dark. No stock blue Adwaita look anywhere.
2. **Wordmark font**: new class `.ff-wordmark` = `"Noto Serif", serif`, italic, weight 700,
   slight letter-spacing; `window.py` adds it to the "Freeflow" sidebar label (keep `title-2`).
   (No font downloads — Noto Serif is installed; Sentient/Fontshare bundling is a later upgrade.)
3. `app.py` calls `apply_style(dark=cfg.dark)`. (Onboarding's call is agent D's file — D makes
   the same one-line change there.)

## Models pane (agent B) — downloadable models

**STT (whisper ggml):** picking a model that `model_path_for()` can't find no longer just says
"run install.sh" — show a `Download <name>` pill + `Gtk.ProgressBar`. Threaded download from the
HF URL above into `download_dir(cfg)` = `Path(cfg.model_path).parent` if set else
`~/.local/share/freeflow/models` (mkdir ok). Write `<file>.part`, rename on success, delete on
failure. Progress fraction from Content-Length (pulse if absent). On success:
`ctx.save(model_path=<new path>)`, refresh pills, clear hint. On failure: hint shows the error.
Pure helpers `model_url(name)`, `download_dir(cfg)` + a download function with injectable
`urlopen` → headless tests. Only one download at a time (disable pills while running).

**Ollama:** `ollama_models(url) -> list[str]` via GET `/api/tags` (names, `:latest` normalized).
If the entered cleanup model isn't in that list, show a `Pull <model>` pill + progress bar:
POST `/api/pull` `{"name": ..., "stream": true}`, read NDJSON lines, fraction =
`completed/total` when both present else pulse + status text. Localhost only. Threaded,
GLib.idle_add. Pure helper `parse_pull_line(line) -> (status, fraction|None)` → headless tests.

**Cleanup explanation:** replace the terse desc with a short plain-English block:
cleanup = a local Ollama pass that strips filler words (um, uh, like), fixes punctuation and
capitalization, and applies your tone; OFF = the raw transcription is typed exactly as heard;
if Ollama is offline or slower than `cleanup_timeout`, Freeflow falls back to the raw text —
dictation never blocks on cleanup.

## General + Tone panes (agent C)

1. **Dark mode switch** in General (name `switch-dark`), after "Paste result":
   `ctx.save(dark=sw.get_active(), _restart=False)` then
   `from freeflow.gui.style import apply_style; apply_style(dark=sw.get_active())` — live, no
   restart banner. Title "Dark mode", desc "Warm dark theme; applies instantly".
2. **Tone explanations** in Tone & Apps: a "What the tones mean" card ABOVE the category rows.
   For the sample dictation `“um so basically can you uh send me the report by friday”` show a
   static (NO Ollama call) row per tone — one-line meaning + example in a lavender pill:
   - **Formal** — full sentences, no contractions, polite: *“Could you please send me the report
     by Friday? Thank you.”*
   - **Neutral** — clean and direct, contractions fine: *“Can you send me the report by Friday?”*
   - **Casual** — relaxed, chat-style: *“hey, can you send me the report by friday?”*
   Fillers are removed by cleanup in every tone; tone only changes the voice.
   Expose the data as `TONE_EXPLANATIONS: list[(tone, meaning, example)]` → headless test.
3. `GuiContext.save` `_restart` param per interface above (+ test: `_restart=False` doesn't set
   `restart_needed` / call the hook, still persists).

## Onboarding + install/uninstall (agent D)

Goal: someone who has NEVER used a local speech-to-text model installs, understands, and can
fully remove Freeflow without reading source.

1. **Onboarding step 0 — "What is Freeflow?"** (new first step, before Permissions): plain-English
   card: *your voice is transcribed on this machine by whisper.cpp (a local speech model — no
   cloud, no account, nothing leaves your computer), then a small local AI (Ollama) tidies the
   words up. Hold the hotkey, talk, release — the text is typed where your cursor is.* Include a
   3-line "hold → talk → release" visual (labels/emoji are fine). Keep the existing 5 steps after
   it (they become steps 2–6). Also: `apply_style(dark=cfg.dark)` at startup.
2. **`install.sh` UX pass:** print a numbered plan up front (what will be installed and WHERE:
   whisper.cpp build dir, model file path, systemd user unit, config path), ask one y/N before
   touching anything, per-step ✓/✗ progress, and end with "next steps" (run onboarding, the
   hotkey, how to uninstall). Keep it idempotent. `bash -n` must pass.
3. **`uninstall.sh` (new):** removes exactly what install.sh created — stops+disables the user
   unit, removes unit file, binaries/venv it installed, downloaded models (ASK before deleting
   models and config/history separately — they're the user's data), prints each path before
   removal, `--dry-run` flag that only prints. Never touches `~/.local/share/whisper-dictation`
   (the OLD daemon) or anything it didn't create. `bash -n` must pass.
4. **README:** a "How it works (no cloud)" section in plain English + a 3-command Quickstart +
   an Uninstall section pointing at `uninstall.sh`.
5. Tests: onboarding step-0 text present + step order (existing test file); new
   `tests/test_install_scripts.py`: `bash -n` both scripts, `--dry-run` uninstall on a fake
   HOME deletes nothing and mentions the unit + model paths, and uninstall never references
   `whisper-dictation`.
