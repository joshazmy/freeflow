"""Freeflow config: TOML file + FREEFLOW_* env overrides, all with sane defaults."""
import os
import re
import tempfile
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

CONFIG_DIR = Path("~/.config/freeflow").expanduser()


@dataclass
class Config:
    whisper_bin: str = ""          # path to whisper-cli
    model_path: str = ""           # path to ggml model
    server: str = "127.0.0.1:8765"  # whisper-server; "" disables fast path
    language: str = "en"            # "auto" for multilingual
    threads: int = 8
    keys: str = "KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT"   # chord
    hands_free: bool = True         # double-tap chord toggles continuous mode
    paste: bool = True              # clipboard-paste delivery vs per-char typing
    cleanup: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:1.7b"
    cleanup_timeout: float = 4.0
    dictionary_path: str = str(CONFIG_DIR / "dictionary.txt")
    overlay: str = "auto"            # "auto" | "notify" | "off"
    tone_overrides: dict = field(default_factory=dict)  # app_class(lower) -> formal|casual|neutral
    media_pause: bool = True
    history: bool = True     # record dictations to a local history file
    dark: bool = False       # warm dark theme; applied live via gui.style.apply_style


def _parse_env_value(raw: str, typ):
    if typ is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if typ is int:
        return int(raw)
    if typ is float:
        return float(raw)
    return raw


def load(path: str | None = None) -> Config:
    cfg_path = Path(path).expanduser() if path else (CONFIG_DIR / "config.toml")
    data = {}
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            data = tomllib.load(f)

    valid = {f.name: f.type for f in fields(Config)}
    kwargs = {k: v for k, v in data.items() if k in valid}
    cfg = Config(**kwargs)

    # env overrides win, one FREEFLOW_<UPPERFIELD> per field except tone_overrides
    for f in fields(Config):
        if f.name == "tone_overrides":
            continue
        env_name = f"FREEFLOW_{f.name.upper()}"
        if env_name in os.environ:
            setattr(cfg, f.name, _parse_env_value(os.environ[env_name], f.type))

    return cfg


_DEFAULT_TOML = """\
# Freeflow configuration. All keys optional -- unset keys use built-in defaults.

# Path to whisper-cli binary (fallback transcription path).
whisper_bin = ""

# Path to the ggml whisper model.
model_path = ""

# whisper-server host:port for the fast HTTP transcription path. Empty string disables it.
server = "127.0.0.1:8765"

# Transcription language, or "auto" for multilingual detection.
language = "en"

# CPU threads for the whisper-cli fallback.
threads = 8

# Trigger chord: comma-separated evdev key names, all must be held to start recording.
keys = "KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT"

# Double-tap the chord quickly to toggle continuous (hands-free) recording.
hands_free = true

# Deliver text via clipboard + paste (fast) instead of per-character typing.
paste = true

# Run the Ollama cleanup pass (fillers, punctuation, tone) after transcription.
cleanup = true

# Ollama server base URL.
ollama_url = "http://127.0.0.1:11434"

# Ollama model used for the cleanup pass.
ollama_model = "qwen3:1.7b"

# Max seconds to wait on the cleanup call before giving up and using raw text.
cleanup_timeout = 4.0

# Path to the user dictionary file (forced spellings).
dictionary_path = "~/.config/freeflow/dictionary.txt"

# Overlay UI: "auto" (pill, falls back to notify), "notify", or "off".
overlay = "auto"

# Pause/resume media playback around a dictation.
media_pause = true

# Record dictations to a local history file (~/.local/share/freeflow/history.jsonl).
history = true

# Warm dark theme (applies live from the GUI's General pane).
# dark = false

# Per-app tone overrides, e.g. tone_overrides.slack = "casual"
[tone_overrides]
"""


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    for raw, esc in (("\\", "\\\\"), ('"', '\\"'), ("\n", "\\n"), ("\r", "\\r"), ("\t", "\\t")):
        s = s.replace(raw, esc)
    return '"' + s + '"'


def save_values(updates: dict, path: str | None = None) -> Path:
    """Write changed keys back to the TOML file, editing lines in place so the
    default file's comments survive. tone_overrides is replaced wholesale;
    other [sections] are preserved verbatim."""
    cfg_path = Path(path).expanduser() if path else (CONFIG_DIR / "config.toml")
    if not cfg_path.exists():
        save_default(str(cfg_path))
    lines = cfg_path.read_text(encoding="utf-8").splitlines()

    header = re.compile(r"^\s*\[")
    first_table = next((i for i, l in enumerate(lines) if header.match(l)), len(lines))
    root, rest = lines[:first_table], lines[first_table:]

    # drop the [tone_overrides] section from rest (regenerated below); keep other sections
    kept, in_tones = [], False
    for line in rest:
        if header.match(line):
            in_tones = line.strip() == "[tone_overrides]"
        if not in_tones:
            kept.append(line)

    tones = updates.get("tone_overrides", load(str(cfg_path)).tone_overrides)

    flat = {k: v for k, v in updates.items() if k != "tone_overrides"}
    for key, val in flat.items():
        pat = re.compile(rf"^\s*{re.escape(key)}\s*=")
        for i, line in enumerate(root):
            if pat.match(line):
                root[i] = f"{key} = {_toml_value(val)}"
                break
        else:
            root.append(f"{key} = {_toml_value(val)}")   # root table, before any [section]

    out = "\n".join(root).rstrip("\n") + "\n"
    if kept:
        out += "\n" + "\n".join(kept).strip("\n") + "\n"
    out += "\n[tone_overrides]\n"
    out += "".join(f"{_toml_value(k)} = {_toml_value(v)}\n" for k, v in tones.items())

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=cfg_path.parent, prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(out)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, cfg_path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    return cfg_path


def save_default(path: str | None = None) -> Path:
    cfg_path = Path(path).expanduser() if path else (CONFIG_DIR / "config.toml")
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(_DEFAULT_TOML)
    return cfg_path
