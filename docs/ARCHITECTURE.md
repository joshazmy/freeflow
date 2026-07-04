# Freeflow — Architecture & Interface Contract (v1)

**This file is the coordination contract for parallel build agents. Do not deviate from the
signatures below — other modules are being written against them concurrently.**

Freeflow = open-source, 100% local Wispr Flow clone. Linux (Wayland) first, macOS adapter later.
Python 3.11+, managed with `uv`. Runtime deps: `evdev` only (Linux). Everything else is stdlib
(`urllib` for HTTP — no `requests`). Optional: `gi` (GTK4 + gtk4-layer-shell) for the pill overlay.

## Pipeline (one dictation)

```
hold chord → record (pw-record 16k mono s16 wav)
release    → transcribe (whisper-server HTTP fast path, whisper-cli fallback, dictionary hint words)
           → hallucination filter (short clips / known silence outputs dropped)
           → deterministic command pass ("press enter" trailing → flag; "new line/paragraph" → \n)
           → dictionary.apply (forced spellings)
           → context tone (active window class → formal/casual/neutral)
           → cleanup via Ollama (filler removal, Backtrack, punctuation, lists, tone) — on ANY
             failure or timeout return the pre-cleanup text unchanged (graceful degrade)
           → deliver (wl-copy + Ctrl+V paste; per-char ydotool type fallback) → optional Enter
```

Seed implementation for record/deliver/chord logic: `~/.local/share/whisper-dictation/listen.py`
(proven on this machine — adapt, don't reinvent).

## Repo layout

```
pyproject.toml            # name=freeflow, [project.scripts] freeflow = "freeflow.cli:main"
install.sh                # one-command installer (Linux)
README.md
docs/ARCHITECTURE.md      # this file
docs/MACOS.md             # macOS adapter plan (v1.1, not built yet)
src/freeflow/
  __init__.py             # __version__ = "0.1.0"
  config.py
  engine.py
  transcribe.py
  cleanup.py
  dictionary.py
  context.py
  overlay.py
  pill.py                 # GTK4 layer-shell pill subprocess entrypoint (python -m freeflow.pill)
  cli.py
  platform/
    __init__.py           # get_platform() -> LinuxPlatform (sys.platform check; darwin raises NotImplementedError pointing at docs/MACOS.md)
    base.py               # Platform ABC
    linux.py
systemd/freeflow.service  # user unit template (installed by install.sh)
tests/                    # pytest; mock all subprocess/HTTP; integration tests marked @pytest.mark.integration
```

## Pinned interfaces

### config.py
```python
CONFIG_DIR = Path("~/.config/freeflow").expanduser()

@dataclass
class Config:
    whisper_bin: str          # path to whisper-cli
    model_path: str           # path to ggml model
    server: str               # "127.0.0.1:8765" whisper-server; "" disables fast path
    language: str = "en"      # "auto" for multilingual
    threads: int = 8
    keys: str = "KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT"   # chord
    hands_free: bool = True   # double-tap chord toggles continuous mode
    paste: bool = True        # clipboard-paste delivery vs per-char typing
    cleanup: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:1.7b"
    cleanup_timeout: float = 4.0
    dictionary_path: str = str(CONFIG_DIR / "dictionary.txt")
    overlay: str = "auto"     # "auto" (pill, fallback notify) | "notify" | "off"
    tone_overrides: dict[str, str] = field(default_factory=dict)  # app_class(lower) -> formal|casual|neutral
    media_pause: bool = True

def load(path: str | None = None) -> Config      # TOML at CONFIG_DIR/config.toml; missing file/keys -> defaults; FREEFLOW_* env overrides win
def save_default(path: str | None = None) -> Path  # write commented default config if absent, return path
```

### transcribe.py
```python
def transcribe(wav_path: str, cfg: Config, hint_words: Sequence[str] = ()) -> str
# server fast path: POST multipart to http://{cfg.server}/inference (temperature=0.0,
#   response_format=text, prompt=" ".join(hint_words) if any) via urllib
# fallback: [cfg.whisper_bin, -m, cfg.model_path, -f, wav, -l, cfg.language, -t, str(threads),
#   -nt, -np] (+ --prompt with hint words). Returns "" on total failure. Whitespace-normalized.

HALLUCINATIONS: frozenset[str]   # copy the set from listen.py
def is_hallucination(text: str) -> bool
MIN_WAV_BYTES: int               # 44 + int(0.35 * 32000)
```

### dictionary.py
```python
class Dictionary:
    def __init__(self, path: str): ...   # missing file => empty; auto-creates parent dir on add
    @property
    def words(self) -> list[str]         # canonical spellings (right-hand sides)
    def add(self, entry: str) -> None    # "Hyprland" or "hyperland->Hyprland"
    def remove(self, entry: str) -> None
    def apply(self, text: str) -> str    # case-insensitive whole-word replace of wrong->right pairs
                                         # AND of case-variants of plain words to canonical spelling
```
File format: one entry per line; `wrong->right` or plain `CanonicalWord`. Lines starting `#` ignored.

### context.py
```python
def active_app() -> tuple[str, str]   # (app_class, window_title), lowercased class; ("","") if unknown
# detection order: hyprctl activewindow -j → swaymsg -t get_tree (focused) → give up
def tone_for(app_class: str, title: str, cfg: Config) -> str   # "formal" | "casual" | "neutral"
```
Built-in category map (cfg.tone_overrides wins): email (thunderbird, evolution, betterbird, or
title contains gmail/proton mail) → formal; work chat (slack, teams) → formal; personal chat
(discord, telegram, signal, whatsapp, element) → casual; everything else → neutral.

### cleanup.py
```python
def clean(text: str, tone: str, cfg: Config, hint_words: Sequence[str] = ()) -> str
```
- POST {cfg.ollama_url}/api/chat, model=cfg.ollama_model, stream=False, `"think": False`
  (qwen3 REQUIRES this or it emits reasoning), options={"temperature": 0.1},
  total wall-clock ≤ cfg.cleanup_timeout via urllib timeout — on timeout/HTTP error/empty or
  degenerate response return `text` unchanged. NEVER raise.
- System prompt implements Wispr Flow behavior, in this order of importance:
  1. Remove fillers (um, uh, like-as-filler, you know) and stutters/duplicated words.
  2. **Backtrack**: self-corrections collapse to final intent — "budget 50K, actually make that
     75K" → "budget 75K". Trigger words: actually/wait/no/scratch that/I mean — ONLY when they
     signal correction ("I actually enjoyed it" stays).
  3. Punctuate + capitalize naturally. Spoken punctuation names become marks: comma, period,
     question mark, exclamation point, em dash, new line, new paragraph, quote/unquote.
  4. Spoken enumerations ("one apples two bananas") → numbered/bulleted list lines.
  5. Tone register: formal → complete sentences, proper punctuation. casual → lowercase-friendly,
     no trailing period on final short sentence. neutral → just clean.
  6. NEVER add content, never answer questions in the text, never translate; output ONLY the
     rewritten text, no quotes/preamble.
- Sanity guard: if result is empty, or >3x or <0.25x input length, return input unchanged.

### overlay.py
```python
class Overlay:
    def __init__(self, mode: str): ...          # "auto"|"notify"|"off"
    def listening(self) -> None                  # show pill / 🎙 notification
    def processing(self) -> None                 # pill state change / no-op for notify
    def done(self) -> None                       # hide pill
    def error(self, msg: str) -> None            # brief notification always (unless off)
    def close(self) -> None
```
"auto": spawn `[sys.executable, "-m", "freeflow.pill", "listening"]` subprocess, send state via
SIGUSR1 (processing) and SIGTERM (done); if pill exits ≠0 immediately, permanently fall back to
notify for the session. pill.py: GTK4 + gtk4-layer-shell bottom-center pill, small dark rounded
rect, white animated bars while listening, static dots while processing; exits on SIGTERM. If gi
import fails → sys.exit(3).
"notify": notify-send -a Freeflow (like listen.py). "off": error() only prints to log.

### platform/base.py
```python
class Platform(ABC):
    def record_start(self, wav_path: str) -> None
    def record_stop(self) -> None                 # must flush a valid WAV header
    def deliver(self, text: str, cfg: Config) -> None
    def press_enter(self) -> None
    def media_pause(self) -> bool                 # True if it paused something
    def media_resume(self) -> None
    def watch_keys(self, cfg: Config, on_start: Callable, on_stop: Callable) -> None
    # blocking loop. Hold semantics: full chord down -> on_start, any key up -> on_stop.
    # Hands-free (cfg.hands_free): double full-chord tap within 0.4s with <0.3s hold each ->
    # toggle mode: on_start now, next single chord tap -> on_stop.
```

### platform/linux.py
`class LinuxPlatform(Platform)` — port listen.py behavior: pw-record w/ pactl default source,
SIGINT flush; wl-copy + `ydotool key 29:1 47:1 47:0 29:0` paste, `ydotool type` fallback;
`ydotool key 28:1 28:0` for Enter; playerctl media; evdev chord watcher skipping
virtual/ydotool devices, device-unplug tolerant. YDOTOOL_SOCKET default /run/ydotoold.socket.

### engine.py
```python
class Engine:
    def __init__(self, cfg: Config): ...   # builds platform, overlay, dictionary
    def run(self) -> None                  # main loop: platform.watch_keys(cfg, self._start, self._stop)
    def _start(self) -> None               # media pause, overlay.listening, record_start
    def _stop(self) -> None                # record_stop, overlay.processing, pipeline, deliver, overlay.done, media resume
    def process(self, raw: str) -> tuple[str, bool]   # PURE, testable: (final_text, press_enter)
    # process(): press-enter trailing detect (regex, strip) → "new line/new paragraph" spoken at
    # boundaries when cleanup disabled (cleanup handles it otherwise) → dictionary.apply →
    # tone from context.active_app + tone_for → cleanup.clean if cfg.cleanup → return
```
Recording to `$XDG_RUNTIME_DIR/freeflow/rec.wav`. Clips < MIN_WAV_BYTES or hallucinations → no-op.

### cli.py
argparse subcommands:
- `freeflow run` — Engine(load()).run()
- `freeflow status` — checks & prints: config path, whisper server reachable?, whisper-cli exists?,
  model exists?, ollama reachable + model present?, ydotool socket?, systemd unit active? Exit 0/1.
- `freeflow config` — print effective config; `freeflow config --init` writes default file
- `freeflow dictionary add|remove|list [entry]`
- `freeflow test "some text"` — run process() pipeline on given text (no audio) and print result
- `freeflow version`

## Testing rules
- pytest, tests mock subprocess.run/Popen and urllib (monkeypatch) — no real audio/GPU in unit tests.
- Real-Ollama / real-whisper tests exist but marked `@pytest.mark.integration` (skipped unless
  `--integration` / `FREEFLOW_INTEGRATION=1`).
- Every module gets a focused test file. Engine.process() is the main behavioral surface — cover
  press-enter, dictionary substitution, cleanup-degrade (mock urllib failure → raw text out).

## Hard rules (from the project brief)
- 100% local. No cloud calls anywhere. No telemetry. No accounts. No Electron.
- Cleanup failure NEVER blocks dictation — raw text must still deliver.
- Don't touch `~/.local/share/whisper-dictation` (the existing daemon keeps running).
- Comments/docs in plain English; README written for a stranger.
