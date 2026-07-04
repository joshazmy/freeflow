"""Freeflow config: TOML file + FREEFLOW_* env overrides, all with sane defaults."""
import os
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

# Per-app tone overrides, e.g. tone_overrides.slack = "casual"
[tone_overrides]
"""


def save_default(path: str | None = None) -> Path:
    cfg_path = Path(path).expanduser() if path else (CONFIG_DIR / "config.toml")
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(_DEFAULT_TOML)
    return cfg_path
