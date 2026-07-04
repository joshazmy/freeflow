"""Speech-to-text: whisper-server HTTP fast path, whisper-cli subprocess fallback.

Never raises -- any failure (server down, binary missing, timeout) degrades to "".
"""
from __future__ import annotations

import subprocess
import urllib.error
import urllib.request
import uuid
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from freeflow.config import Config

# Exact transcripts whisper hallucinates from silence/near-silence.
HALLUCINATIONS = frozenset({
    "you", "thank you", "thank you.", "thanks for watching", "thanks for watching!",
    "thank you for watching", "thank you for watching.", "bye", "bye.", ".", "...",
    "you.", "okay", "okay.", "thank you very much", "thank you very much.",
})

# 16kHz mono s16 = 32000 bytes/sec; ~0.35s of audio + a 44-byte WAV header.
MIN_WAV_BYTES = 44 + int(0.35 * 32000)


def is_hallucination(text: str) -> bool:
    key = text.strip().lower().rstrip(" .!?,")
    return not key or key in HALLUCINATIONS


def _post_server(server: str, wav_path: str, hint_words: Sequence[str]) -> str:
    """POST wav to whisper-server /inference as multipart/form-data, via urllib only."""
    boundary = uuid.uuid4().hex
    fields = [("temperature", "0.0"), ("response_format", "text")]
    if hint_words:
        fields.append(("prompt", " ".join(hint_words)))

    with open(wav_path, "rb") as f:
        wav_bytes = f.read()

    parts = []
    for name, value in fields:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="rec.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n".encode()
        + wav_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        f"http://{server}/inference",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def transcribe(wav_path: str, cfg: "Config", hint_words: Sequence[str] = ()) -> str:
    if getattr(cfg, "server", ""):
        try:
            text = _post_server(cfg.server, wav_path, hint_words)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            text = ""
        if text.strip():
            return " ".join(text.split()).strip()

    cmd = [
        cfg.whisper_bin, "-m", cfg.model_path, "-f", wav_path,
        "-l", cfg.language, "-t", str(cfg.threads), "-nt", "-np",
    ]
    if hint_words:
        cmd += ["--prompt", " ".join(hint_words)]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if r and r.stdout:
        return " ".join(r.stdout.split()).strip()
    return ""
