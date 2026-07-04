# Freeflow

Freeflow is Wispr Flow, but open source and 100% local. Hold a key, speak, and cleaned-up text
lands in whatever app has focus. Nothing you say ever leaves your machine — no cloud API, no
account, no telemetry.

## How it feels to use

Hold **⌃ Ctrl + ⌥ Alt + ⇧ Shift**, say:

> "um so basically can you uh send the the file tomorrow"

Release the keys. This appears at your cursor:

> "Can you send the file tomorrow."

Fillers gone, stutter collapsed, punctuated, capitalized — pasted straight into your editor,
browser, chat, whatever you were typing into.

Double-tap the chord instead of holding it and Freeflow switches to hands-free continuous mode —
tap it again to stop.

## How it works (no cloud)

Never used a local speech model before? Here's the whole thing in plain English:

1. **You hold the hotkey and talk.** Freeflow records audio only while the key is held.
2. **Your voice is transcribed on your own machine** by [whisper.cpp](https://github.com/ggerganov/whisper.cpp),
   a local speech model — no cloud API, no account, nothing you say leaves your computer.
3. **A small local AI ([Ollama](https://ollama.com)) tidies the words up** — removes "um"/"uh",
   fixes punctuation and capitalization, applies your tone. If Ollama is off or slow, you still get
   the raw transcription; dictation never blocks on cleanup.
4. **You release the key and the cleaned text is typed** wherever your cursor is.

Both the speech model and the cleanup model run on `localhost`. The only network access is when
*you* choose to download a model. Nothing is sent anywhere else, ever.

## Quickstart

```
git clone <this-repo> && cd freeflow
./install.sh          # prints a plan, asks once, then installs everything locally
freeflow onboarding   # 6-step first-run setup (starts with "What is Freeflow?")
```

Then hold **⌃ Ctrl + ⌥ Alt + ⇧ Shift**, speak, and release. To remove everything later, run
`./uninstall.sh`.

## Features

| Feature | Status |
|---|---|
| Hold-to-talk dictation | ✅ v1 |
| Hands-free double-tap mode | ✅ v1 |
| GPU-accelerated transcription (whisper.cpp, CUDA/Vulkan) | ✅ v1 |
| AI cleanup: filler removal, punctuation, lists | ✅ v1 |
| Backtrack (self-correction collapsing, "actually make that 75K") | ✅ v1 |
| Spoken punctuation ("comma", "new paragraph") | ✅ v1 |
| Personal dictionary (forced spellings) | ✅ v1 |
| Per-app tone (formal for email/Slack, casual for Discord) | ✅ v1 |
| Pill overlay (listening/processing indicator) | ✅ v1 |
| Command Mode (voice commands, not just dictation) | 🔜 v2 |
| Transcript history | 🔜 v2 |
| Auto-learn dictionary from corrections | 🔜 v2 |
| macOS support | 🔜 v2 (see [docs/MACOS.md](docs/MACOS.md)) |

## Install

The installer installs freeflow FROM this checkout (it needs `pyproject.toml` and
`systemd/freeflow.service` alongside it), so it can't be curl-piped straight into bash — clone
first, then run it as a local file:

```
git clone <this-repo>
cd freeflow
less install.sh   # read it — it's plain, commented shell
./install.sh
```

It will ask for `sudo` confirmation before installing anything and print what it's doing at each
step.

Supports Fedora (dnf), Ubuntu/Debian (apt), and Arch (pacman). Wayland only for now.

## GUI

Optional native GTK4 settings app (no Electron, no webview — 100% local, same as everything
else here):

```
freeflow onboarding   # first-run setup: permissions, mic test, shortcut, language, try it
freeflow gui          # settings window: general, dictionary, tone & apps, models, privacy, about
freeflow tray         # system-tray icon: open settings, pause/resume dictation, quit
```

Needs GTK4 + PyGObject (`install.sh` offers to install these, or `dnf install gtk4
python3-gobject` / your distro's equivalent) and, for the tray icon only, the AppIndicator3
typelib (`dnf install libappindicator-gtk3`, apt: `gir1.2-ayatanaappindicator3-0.1`,
pacman: `libappindicator-gtk3` — no pip packages). Fonts fall back to the system serif
and sans-serif if `Sentient`/`General Sans` aren't installed — no CDN fetch either way.

## Configuration

Edit `~/.config/freeflow/config.toml` (created on first run by `freeflow config --init`):

| Key | Default | Meaning |
|---|---|---|
| `whisper_bin` | (auto-detected) | path to `whisper-cli` |
| `model_path` | (auto-picked) | path to the ggml model |
| `server` | `"127.0.0.1:8765"` | whisper-server fast path; empty string disables it |
| `language` | `"en"` | `"auto"` for multilingual |
| `threads` | `8` | whisper-cli thread count |
| `keys` | `"KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT"` | hold-to-talk chord |
| `hands_free` | `true` | double-tap chord toggles continuous mode |
| `paste` | `true` | clipboard-paste delivery vs per-character typing |
| `cleanup` | `true` | run AI cleanup via Ollama |
| `ollama_url` | `"http://127.0.0.1:11434"` | Ollama endpoint |
| `ollama_model` | `"qwen3:1.7b"` | cleanup model |
| `cleanup_timeout` | `4.0` | seconds before falling back to raw text |
| `dictionary_path` | `~/.config/freeflow/dictionary.txt` | forced-spelling word list |
| `overlay` | `"auto"` | `"auto"` (pill, falls back to notify) \| `"notify"` \| `"off"` |
| `tone_overrides` | `{}` | app_class → `formal`/`casual`/`neutral` |
| `media_pause` | `true` | pause music while dictating |

## Troubleshooting

- `freeflow status` — checks config, whisper server/binary/model, Ollama, ydotool socket, and the
  systemd unit in one shot. Start here.
- **No text appears / paste fails**: check `/run/ydotoold.socket` exists. If the installer added
  you to the `input` group, you must **log out and back in** once before it takes effect.
- **Wayland only**: Freeflow relies on `wl-copy`, `hyprctl`/`swaymsg`, and evdev — it does not
  support X11.
- **AI cleanup silently not happening**: cleanup failures degrade gracefully to raw transcribed
  text by design (never blocks dictation) — check `ollama list` and `freeflow status` to see why.

## Uninstall

`./uninstall.sh` is the mirror of the installer — it removes exactly what `install.sh` created and
nothing else:

```
./uninstall.sh --dry-run   # show what WOULD be removed, delete nothing
./uninstall.sh             # actually remove
```

It stops and disables the `freeflow` user service, removes the unit file, the whisper.cpp build,
and the installed program. Your **downloaded models** and your **config + dictionary + history**
are your data, so it asks about each one separately before deleting — and prints every path first.
It never touches anything Freeflow didn't create.

## Privacy

Everything runs on your machine: audio never leaves it, transcription is local whisper.cpp,
cleanup is a local Ollama model. No cloud calls, no telemetry, no accounts, ever.

This holds as long as `server` and `ollama_url` point at localhost (the default) — if you
repoint either at a remote host, your dictations are sent there.

## License

MIT.

## Credits

Built on [whisper.cpp](https://github.com/ggerganov/whisper.cpp) and [Ollama](https://ollama.com).
Inspired by [Wispr Flow](https://wisprflow.ai) — Freeflow is an independent open-source project,
not affiliated with or endorsed by Wispr.
