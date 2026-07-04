# macOS adapter plan (v1.1, not built yet)

Freeflow's core (`engine.py`, `transcribe.py`, `cleanup.py`, `dictionary.py`) is platform-agnostic.
Only `platform.Platform` needs a macOS implementation. This is the honest engineering plan, not
a promise of when it ships.

## Files to add

- `src/freeflow/platform/macos.py` — `class MacPlatform(Platform)`, same ABC as `linux.py`.
- `src/freeflow/platform/macos_helper.swift` (or `.m`) — tiny compiled helper for the CGEventTap
  hotkey watcher (Python's CG bindings via `pyobjc` are workable but a compiled helper is more
  reliable for a blocking low-level event tap).
- `src/freeflow/platform/macos_record.py` — wraps the audio capture command (see below).
- `packaging/homebrew/freeflow.rb` — Homebrew formula for `brew install freeflow`.

## Per-method plan

- **`watch_keys` (hotkey capture)**: `Quartz.CGEventTapCreate` listening for the chord's modifier
  flags. Requires the user grant **Accessibility** permission (System Settings → Privacy &
  Security → Accessibility) to the terminal/app bundle — there is no way around this prompt.
  Hold/double-tap timing logic ports directly from `linux.py`'s evdev version.

- **`record_start` / `record_stop` (audio)**: no `pw-record` on macOS. Options considered:
  - `sox` (`rec`) — simplest, but not preinstalled; adds a brew dependency.
  - `ffmpeg -f avfoundation -i ":0"` — also not preinstalled, heavier dependency.
  - AVFoundation directly via a tiny Swift CLI helper (`AVAudioRecorder` to a 16kHz mono WAV) —
    no extra runtime dependency once compiled, matches "one command, it just works" better.
  Plan: ship the Swift helper, fall back to `sox` if present and the helper isn't built (e.g. dev
  checkout without Xcode).

- **`deliver` (paste text)**: `pbcopy` for clipboard, then synth ⌘V via
  `CGEventCreateKeyboardEvent` (kVK_ANSI_V + cmd flag), posted with `CGEventPost`. Same
  Accessibility permission as the hotkey tap covers this. No per-char typing fallback planned for
  v1.1 — clipboard paste only, matches macOS conventions better than `ydotool type` anyway.

- **`media_pause` / `media_resume`**: no `playerctl` equivalent. `osascript` can drive specific
  apps (`tell application "Music" to pause`) but there is no universal "pause whatever's playing"
  API without private frameworks (MediaRemote is private, requires entitlements Apple doesn't
  grant to third parties outside specific contexts). Plan: best-effort `osascript` against Music/
  Spotify by name if running, otherwise no-op — document the limitation, don't fake it.

- **Pill overlay**: GTK4 + layer-shell doesn't exist on macOS. Plan: a small AppKit `NSPanel`
  (borderless, floating, `.statusBar` level) driven from a tiny Swift or PyObjC helper subprocess,
  same subprocess/signal protocol as `pill.py` (SIGUSR1 = processing, SIGTERM = done) so
  `overlay.py`'s process-management logic doesn't need to change.

- **Packaging**: Homebrew formula depending on `whisper-cpp` (already in homebrew-core) and
  `ollama` (already in homebrew-core, cask), installing the Python package + the compiled Swift
  helper binaries, and a LaunchAgent plist (macOS's systemd-user equivalent) instead of
  `systemd/freeflow.service`.

## What can't be verified from this Linux machine

- Whether `CGEventTapCreate` actually receives events without SIP/Accessibility quirks per macOS
  version — needs a real Mac + manual permission grant, can't be tested headless.
- AVFoundation audio capture latency/format correctness (sample rate, channel layout matching
  whisper.cpp's expected 16kHz mono s16 input).
- Whether Homebrew's `whisper-cpp` formula is built with Metal/Core ML acceleration by default
  (affects the GPU-probe equivalent step in a future `install-macos.sh`).
- Any Gatekeeper/notarization requirements for distributing the compiled Swift helper outside the
  App Store.

None of this blocks v1 (Linux). This file exists so a future contributor with a Mac has a
concrete starting point instead of re-deriving the plan.
