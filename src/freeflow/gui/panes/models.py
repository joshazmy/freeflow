"""Models pane: speech-to-text model picker + cleanup/Ollama card."""
from __future__ import annotations

import json
import os
import threading
import urllib.request
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

MODEL_ALTERNATIVES = ["base", "small", "large-v3", "large-v3-turbo"]

CLEANUP_EXPLANATION = (
    "Cleanup runs a local Ollama pass over your transcription: it strips filler words "
    "(um, uh, like), fixes punctuation and capitalization, and applies your tone. "
    "With it OFF, the raw transcription is typed exactly as heard. If Ollama is offline "
    "or slower than your cleanup timeout, Freeflow falls back to the raw text — "
    "dictation never blocks on cleanup."
)


def model_name_from_path(path: str) -> str:
    if not path:
        return ""
    stem = Path(path).stem
    for name in sorted(MODEL_ALTERNATIVES, key=len, reverse=True):
        if name in stem:
            return name
    return stem


def model_path_for(name: str, current_path: str) -> str | None:
    """Sibling ggml file matching `name` in the same directory as current_path, if any."""
    if not current_path:
        return None
    directory = Path(current_path).parent
    if not directory.is_dir():
        return None
    for f in sorted(directory.glob(f"*{name}*.bin")):
        return str(f)
    return None


def model_url(name: str) -> str:
    return f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin"


def download_dir(cfg) -> Path:
    if cfg.model_path:
        return Path(cfg.model_path).parent
    return Path("~/.local/share/freeflow/models").expanduser()


def download_model(url, dest_dir, name, *, urlopen=urllib.request.urlopen, progress=None) -> Path:
    """Stream `url` to `<dest_dir>/<name>.part`, os.replace to ggml-<name>.bin on success.

    progress(fraction) is called with a 0..1 float when Content-Length is known, else None
    (pulse). The .part file is removed on any failure.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    part = dest / f"{name}.part"
    final = dest / f"ggml-{name}.bin"
    try:
        with urlopen(url) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            with open(part, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if progress:
                        progress(got / total if total else None)
        os.replace(part, final)
        return final
    except BaseException:
        if part.exists():
            part.unlink()
        raise


def _normalize(name: str) -> str:
    name = name.strip()
    return name[:-7] if name.endswith(":latest") else name


def ollama_models(url: str, timeout: float = 2.0) -> list[str]:
    """Installed Ollama model names via GET /api/tags, with ':latest' normalized away."""
    with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=timeout) as resp:
        data = json.loads(resp.read())
    return [_normalize(m["name"]) for m in data.get("models", [])]


def parse_pull_line(line: str) -> tuple[str, float | None]:
    """One NDJSON line from /api/pull -> (status, fraction|None)."""
    try:
        data = json.loads(line)
    except (ValueError, TypeError):
        return ("", None)
    status = data.get("status", "")
    completed, total = data.get("completed"), data.get("total")
    if completed is not None and total:
        return (status, completed / total)
    return (status, None)


def pull_model(url, model, *, urlopen=urllib.request.urlopen, progress=None) -> None:
    """POST /api/pull streaming NDJSON; progress(status, fraction) per line. Localhost only."""
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/pull",
        data=json.dumps({"name": model, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as resp:
        for raw in resp:
            line = raw.decode() if isinstance(raw, bytes) else raw
            status, frac = parse_pull_line(line)
            if progress:
                progress(status, frac)


def ollama_connected(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _row(control_left: Gtk.Widget, control_right: Gtk.Widget | None = None) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    control_left.set_hexpand(True)
    row.append(control_left)
    if control_right is not None:
        row.append(control_right)
    return row


def _card(title: str) -> Gtk.Box:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.add_css_class("ff-card")
    heading = Gtk.Label(label=title, xalign=0)
    heading.add_css_class("ff-serif")
    card.append(heading)
    return card


def build(ctx) -> Gtk.Widget:
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

    # --- Speech-to-text card ---
    stt_card = _card("Speech-to-text")

    current_name = model_name_from_path(ctx.cfg.model_path)
    current_label = Gtk.Label(label=f"Model: {current_name or '(none)'}", xalign=0)
    stt_card.append(current_label)

    hint_label = Gtk.Label(label="", xalign=0)
    hint_label.set_name("model-hint")
    hint_label.add_css_class("ff-muted")
    hint_label.set_wrap(True)

    pill_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    pills = []

    def refresh_pills(active_name):
        for b, name in pills:
            if name == active_name:
                b.add_css_class("ff-pill-active")
            else:
                b.remove_css_class("ff-pill-active")

    # download row (hidden until a missing model is picked)
    download_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    download_row.set_name("model-download-row")
    download_btn = Gtk.Button(label="Download")
    download_btn.add_css_class("ff-pill")
    download_btn.set_name("model-download")
    download_progress = Gtk.ProgressBar()
    download_progress.set_name("model-progress")
    download_progress.set_hexpand(True)
    download_row.append(download_btn)
    download_row.append(download_progress)
    download_row.set_visible(False)

    pending = {"name": None}
    downloading = {"active": False}

    def set_pills_sensitive(sensitive):
        for b, _ in pills:
            b.set_sensitive(sensitive)
        download_btn.set_sensitive(sensitive)

    def _dl_done(name, path):
        ctx.save(model_path=path)
        current_label.set_label(f"Model: {name}")
        refresh_pills(name)
        hint_label.set_label("")
        download_row.set_visible(False)
        downloading["active"] = False
        set_pills_sensitive(True)
        return False

    def _dl_fail(msg):
        hint_label.set_label(f"Download failed: {msg}")
        download_row.set_visible(False)
        downloading["active"] = False
        set_pills_sensitive(True)
        return False

    def _dl_progress(frac):
        def upd():
            if frac is None:
                download_progress.pulse()
            else:
                download_progress.set_fraction(frac)
            return False
        GLib.idle_add(upd)

    def start_download(_btn):
        name = pending["name"]
        if not name or downloading["active"]:
            return
        downloading["active"] = True
        set_pills_sensitive(False)
        ddir = download_dir(ctx.cfg)
        url = model_url(name)

        def work():
            try:
                path = download_model(url, ddir, name, progress=_dl_progress)
            except Exception as e:
                GLib.idle_add(_dl_fail, str(e))
                return
            GLib.idle_add(_dl_done, name, str(path))

        threading.Thread(target=work, daemon=True).start()

    download_btn.connect("clicked", start_download)

    for name in MODEL_ALTERNATIVES:
        btn = Gtk.Button(label=name)
        btn.add_css_class("ff-pill")
        btn.set_name(f"model-pill-{name}")
        if name == current_name:
            btn.add_css_class("ff-pill-active")

        def on_pick(_btn, name=name):
            if name == model_name_from_path(ctx.cfg.model_path):
                return
            found = model_path_for(name, ctx.cfg.model_path)
            if found:
                ctx.save(model_path=found)
                current_label.set_label(f"Model: {name}")
                hint_label.set_label("")
                download_row.set_visible(False)
                refresh_pills(name)
            else:
                pending["name"] = name
                download_btn.set_label(f"Download {name}")
                download_progress.set_fraction(0)
                download_row.set_visible(True)
                hint_label.set_label("")

        btn.connect("clicked", on_pick)
        pill_row.append(btn)
        pills.append((btn, name))

    stt_card.append(pill_row)
    stt_card.append(download_row)
    badge = Gtk.Label(label="auto-picked for your GPU")
    badge.add_css_class("ff-muted")
    stt_card.append(badge)
    stt_card.append(hint_label)
    root.append(stt_card)

    # --- Cleanup card ---
    cleanup_card = _card("Cleanup")

    cleanup_sw = Gtk.Switch(active=ctx.cfg.cleanup)
    cleanup_sw.set_name("switch-cleanup")
    cleanup_sw.connect("notify::active", lambda sw, _p: ctx.save(cleanup=sw.get_active()))

    ollama_badge = Gtk.Label(label="…")
    ollama_badge.set_name("ollama-badge")
    ollama_badge.add_css_class("ff-muted")

    status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    status_row.append(ollama_badge)
    cleanup_card.append(_row(status_row, cleanup_sw))

    entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    model_label = Gtk.Label(label="Ollama model:")
    entry = Gtk.Entry()
    entry.set_text(ctx.cfg.ollama_model)
    entry.set_name("entry-ollama-model")

    # pull row (hidden until we know the entered model isn't installed)
    pull_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    pull_row.set_name("pull-row")
    pull_btn = Gtk.Button(label="Pull")
    pull_btn.add_css_class("ff-pill")
    pull_btn.set_name("pull-model")
    pull_progress = Gtk.ProgressBar()
    pull_progress.set_name("pull-progress")
    pull_progress.set_hexpand(True)
    pull_row.append(pull_btn)
    pull_row.append(pull_progress)
    pull_row.set_visible(False)

    pulling = {"active": False}

    def _apply_ollama(installed):
        if installed is None:
            ollama_badge.set_label("offline")
            pull_row.set_visible(False)
            return False
        ollama_badge.set_label("connected")
        model = ctx.cfg.ollama_model
        if not pulling["active"]:
            if _normalize(model) in installed:
                pull_row.set_visible(False)
            else:
                pull_btn.set_label(f"Pull {model}")
                pull_progress.set_fraction(0)
                pull_row.set_visible(True)
        return False

    def refresh_ollama_state():
        def work():
            try:
                installed = ollama_models(ctx.cfg.ollama_url)
            except Exception:
                installed = None
            GLib.idle_add(_apply_ollama, installed)
        threading.Thread(target=work, daemon=True).start()

    def save_if_changed(*_a):
        text = entry.get_text()
        if text != ctx.cfg.ollama_model:
            ctx.save(ollama_model=text)
            refresh_ollama_state()

    entry.connect("activate", save_if_changed)
    focus_controller = Gtk.EventControllerFocus()
    focus_controller.connect("leave", save_if_changed)
    entry.add_controller(focus_controller)
    entry_row.append(model_label)
    entry_row.append(entry)
    cleanup_card.append(entry_row)
    cleanup_card.append(pull_row)

    def _pull_done():
        pulling["active"] = False
        pull_row.set_visible(False)
        ollama_badge.set_label("connected")
        return False

    def _pull_fail(msg):
        pulling["active"] = False
        pull_btn.set_sensitive(True)
        ollama_badge.set_label(f"pull failed: {msg}")
        return False

    def _pull_progress(status, frac):
        def upd():
            if frac is None:
                pull_progress.pulse()
            else:
                pull_progress.set_fraction(frac)
            return False
        GLib.idle_add(upd)

    def start_pull(_btn):
        model = ctx.cfg.ollama_model
        if pulling["active"] or not model:
            return
        pulling["active"] = True
        pull_btn.set_sensitive(False)

        def work():
            try:
                pull_model(ctx.cfg.ollama_url, model, progress=_pull_progress)
            except Exception as e:
                GLib.idle_add(_pull_fail, str(e))
                return
            GLib.idle_add(_pull_done)

        threading.Thread(target=work, daemon=True).start()

    pull_btn.connect("clicked", start_pull)

    desc = Gtk.Label(label=CLEANUP_EXPLANATION, xalign=0)
    desc.add_css_class("ff-muted")
    desc.set_wrap(True)
    cleanup_card.append(desc)

    root.append(cleanup_card)

    refresh_ollama_state()

    return root
