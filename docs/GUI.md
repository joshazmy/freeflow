# GUI Contract (pinned — parallel agents build against this, do not deviate)

Native **GTK4 via PyGObject** (no Electron, no webview — brief rule). The approved look is
`design/mockup.html` (Wispr Flow language): cream `#FFFEF0` background, ink `#111110` text,
white `#FFFFFF` cards with 1px ink borders + hard shadow `3px 3px 0 rgba(17,17,16,.12)`,
radius 20px cards / 999px pills, one lavender accent `#E7D4F9` (active nav item, primary
buttons). Fonts are a *fallback stack* (no CDN, app is 100% local):
display serif `Sentient, P052, Georgia, serif`; UI `General Sans, Inter, Cantarell, sans-serif`.

## Module map & ownership (disjoint — never edit another agent's file)

| File | Owner |
|---|---|
| `gui/__init__.py`, `gui/state.py` (GuiContext — DONE, see below) | orchestrator |
| `gui/style.py`, `gui/window.py`, `gui/app.py`, `gui/panes/__init__.py`, `gui/panes/about.py`, `gui/panes/privacy.py` | agent A |
| `gui/panes/general.py`, `gui/panes/models.py`, `gui/panes/tone.py` | agent B |
| `gui/panes/dictionary.py`, `gui/onboarding.py` | agent C |
| `gui/tray.py`, `cli.py` (edit), `pyproject.toml` (edit), `install.sh` (edit), `README.md` (edit) | agent D |

Tests: one `tests/test_gui_<yourmodule>.py` per module, same owner.

## Shared interfaces (exact — already implemented where marked DONE)

```python
# gui/state.py  (DONE — do not modify)
GuiContext(cfg: Config, config_path: str|None)
ctx.save(**updates)          # persists via config.save_values, mirrors onto ctx.cfg,
                             # sets ctx.restart_needed=True, fires ctx.on_restart_needed
ctx.dictionary               # cached freeflow.dictionary.Dictionary
```

```python
# gui/style.py (agent A)
CSS: str                     # full GTK4 CSS with the tokens above
def apply_style() -> None    # CssProvider on the default display, APPLICATION priority

# every pane module (agents A/B/C)
def build(ctx: GuiContext) -> "Gtk.Widget"   # returns the pane's root widget

# gui/panes/__init__.py (agent A)
PANES = [("general", "General", general.build), ("dictionary", "Dictionary", ...),
         ("tone", "Tone & Apps", ...), ("models", "Models", ...),
         ("privacy", "Data & Privacy", ...), ("about", "About", ...)]   # this order

# gui/window.py (agent A)
class SettingsWindow(Gtk.ApplicationWindow)   # (application=, ctx=) sidebar ListBox + Gtk.Stack
#   wires ctx.on_restart_needed -> reveals a banner "Restart Freeflow to apply changes"
#   with a [Restart now] button -> subprocess systemctl --user restart freeflow (best-effort)

# gui/app.py (agent A)
class FreeflowApp(Gtk.Application)            # application_id "io.github.joshazmy.freeflow"
def main(argv=None) -> int                    # apply_style() then SettingsWindow

# gui/onboarding.py (agent C)
class OnboardingWindow(Gtk.ApplicationWindow) # 5 steps (below)
def main(argv=None) -> int                    # own Gtk.Application id ...".onboarding"
# completing step 5 writes Path(CONFIG_DIR/".onboarded")

# gui/tray.py (agent D)
def main() -> int   # SNI tray via ksni if importable, else print install hint, return 1
```

## Pane content (from the approved mockup — match it)

- **General**: Hotkey row (shows pretty chord from `cfg.keys`, e.g. "⌃ Ctrl + ⌥ Alt + ⇧ Shift (hold)";
  [change] opens a preset dropdown of 3–4 sane chords → `ctx.save(keys=...)`) ·
  Hands-free switch → `hands_free` · Paste result switch → `paste` ·
  Language pill-row (English (auto)=`"en"`… plus "auto") → `language` ·
  Start at login switch → `systemctl --user enable/disable freeflow` (subprocess, best-effort,
  state read via `is-enabled`).
- **Dictionary**: white pill rows listing `ctx.dictionary` entries (`wrong → Right` or plain word),
  ✕ per row → `.remove()`; entry + [Add] → `.add()` (accepts `wrong->right` or plain). Footer hint
  "Corrections you make get suggested here automatically." (static). Cream/ink per Josh's redline —
  NOT dark green.
- **Tone & Apps**: rows Email / Work chat / Personal chat / Everything else, each a 3-way pill
  segment Formal|Neutral|Casual → stored in `tone_overrides` under keys `_email`, `_work_chat`,
  `_personal_chat`, `_default` (leading underscore = category, matches context.tone_for's app
  fallbacks; check `src/freeflow/context.py` and follow what it actually reads — if it only
  reads app-class keys, store categories anyway and note it). Per-app overrides list (app class →
  3-way pill) + [+ Add app] entry row → normal `tone_overrides` keys. Every change `ctx.save(...)`.
- **Models**: Speech-to-text card — current model name derived from `cfg.model_path` filename,
  pill-row of alternatives (base/small/large-v3/large-v3-turbo) that only *shows* which is active;
  picking another shows hint "run install.sh to download models" unless a matching ggml file sits
  in the same dir (then `ctx.save(model_path=...)`). "auto-picked for your GPU" caption.
  Cleanup card — AI-cleanup switch → `cleanup`, Ollama model entry → `ollama_model`, connection
  badge (probe `cfg.ollama_url/api/tags`, 1s timeout, "connected"/"offline").
- **Data & Privacy**: static "100% local." serif headline + 4 check rows (audio never leaves this
  machine / no accounts / no telemetry / works offline) + a mono pill `$ freeflow status → ● all local`.
- **About**: wordmark "Freeflow", `v{__version__} · MIT License`, rows: Source
  github.com/joshazmy/freeflow · Speech engine whisper.cpp · Cleanup engine Ollama.

## Onboarding steps (agent C)

1. **Permissions** — live checks: user in `input` group (`grp`), ydotool socket exists
  (reuse the probe logic style of `cli.cmd_status`); red/green rows + "log out and back in" hint.
2. **Mic test** — [Record 2s] runs `pw-record` to a temp wav (subprocess, 2s), green check if the
  file is non-trivial (>8KB); no playback needed.
3. **Shortcut** — show chord from cfg, same preset picker as General → `ctx.save(keys=...)`.
4. **Language** — pill-row → `ctx.save(language=...)`.
5. **Try it** — entry prefilled "um can you uh send the file", [Simulate dictation] runs
  `Engine(cfg).process(text)` in a thread, shows the cleaned result in a lavender pill.
  Finish → write `.onboarded`, close.

## Rules

- Strict TDD: failing test first, then code; paste real output in your report.
- Test command: `PYTHONPATH=src python3 -m pytest tests/test_gui_<x>.py -q` from repo root.
- GTK tests: `gi = pytest.importorskip("gi")`, then `gi.require_version("Gtk","4.0")`; skip the
  test with `pytest.skip` if `Gtk.init_check()` is falsy (headless CI). Logic that can live
  outside widgets (formatting, probes, tone-key mapping) goes in plain functions — test those
  headless.
- No network calls except localhost probes. No new pip deps except `ksni` as a `[gui]` optional
  extra (agent D). No threads except where the contract says (Ollama probe, Try-it) — use
  `GLib.idle_add` to touch widgets from threads.
- Don't touch `engine.py`, `overlay.py`, `pill.py`, or another agent's files. Don't run the
  full suite (collection imports may race mid-build) — run only your own test files.
