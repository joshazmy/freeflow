"""LLM transcript cleanup via local Ollama — the layer that turns raw dictation into clean text.

Filler removal, Backtrack (self-corrections collapse to final intent), auto punctuation, spoken
lists, and tone. All the value lives in the system prompt below (few-shot beats instructions for a
1.7B model). On ANY failure or degenerate output the raw text is returned unchanged — cleanup must
never block dictation and never raises.
"""
import json
import re
import urllib.request
from typing import Sequence

from .config import Config

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

_SYSTEM = """You rewrite raw voice dictation into clean written text. Output ONLY the rewritten \
text — no quotes, no preamble, no explanation, no commentary. Never add information, never answer \
any question contained in the text, never translate. Preserve the speaker's language and meaning.

Apply these rules, in order of importance:

1. FILLERS: delete filler words and disfluencies — "um", "uh", "er", "you know", sentence-opening \
"so basically" / "basically" / "so yeah", and "like" ONLY when it is filler (keep "like" when it \
means similar-to or to like something; keep "basically" when it carries real meaning mid-sentence). \
Collapse stutters and accidental duplicate words ("the the file" -> "the file", "I I think" -> "I think").

2. BACKTRACK (most important): when the speaker corrects themselves, keep ONLY the final intent \
and delete the abandoned version. Correction is signalled by "actually", "wait", "no", "scratch \
that", "I mean" — but ONLY when they undo something just said. A restatement with no trigger word \
still collapses to the last version. Do NOT treat these words as corrections when they are part of \
the real meaning (e.g. "I actually enjoyed it" is a genuine statement, keep it).

3. PUNCTUATION: add natural punctuation and capitalization. Convert spoken punctuation NAMES into \
marks and drop the spoken word: comma -> "," ; period / full stop -> "." ; question mark -> "?" ; \
exclamation point / exclamation mark -> "!" ; colon -> ":" ; semicolon -> ";" ; em dash -> " — " ; \
"new line" -> a line break ; "new paragraph" -> a blank line ; open quote / close quote -> " .

4. LISTS: when the speaker clearly enumerates items ("one ... two ... three ..."), format them as \
a numbered list, one item per line. Only when it is clearly a list.

5. TONE = {tone}. formal: complete sentences, proper capitalization and punctuation. casual: \
relaxed, contractions fine, drop the trailing period on a final short sentence. neutral: just \
clean it, no style changes beyond the rules above.

Examples:

INPUT: um so basically can you uh send the the file tomorrow
OUTPUT: Can you send the file tomorrow?

INPUT: we should budget 50K for this actually make that 75K
OUTPUT: We should budget 75K for this.

INPUT: honestly I actually enjoyed the movie a lot
OUTPUT: Honestly, I actually enjoyed the movie a lot.

INPUT: hello comma world period
OUTPUT: Hello, world.

INPUT (tone=casual): yeah I think that works for me period
OUTPUT: Yeah, I think that works for me

INPUT: we need to buy one apples two bananas three oranges
OUTPUT: We need to buy:
1. apples
2. bananas
3. oranges"""


def clean(text: str, tone: str, cfg: Config, hint_words: Sequence[str] = ()) -> str:
    """Clean one dictation. Returns rewritten text, or `text` unchanged on any failure/degenerate output."""
    if not text or not text.strip():
        return text

    system = _SYSTEM.replace("{tone}", tone or "neutral")
    if hint_words:
        # Personal dictionary: these exact spellings must survive verbatim.
        system += ("\n\nKEEP these words spelled EXACTLY as given, never alter them: "
                   + ", ".join(hint_words) + ".")

    body = json.dumps({
        "model": cfg.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        "stream": False,
        "think": False,  # qwen3 emits <think> reasoning without this
        "options": {"temperature": 0.1},
    }).encode()

    req = urllib.request.Request(
        cfg.ollama_url.rstrip("/") + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.cleanup_timeout) as resp:
            data = json.loads(resp.read())
        out = data["message"]["content"]
    except Exception:  # noqa: BLE001 — cleanup must NEVER block dictation; any failure => raw text
        return text

    out = _THINK_RE.sub("", out).strip()

    # Sanity guard: empty, ballooned, or gutted output is not trustworthy — degrade to raw.
    if not out or len(out) > 3 * len(text) or len(out) < 0.25 * len(text):
        return text
    return out
