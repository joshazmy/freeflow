"""First-run onboarding wizard: 5 steps per design/mockup.html's #onboarding
screen (docs/GUI.md) - permissions, mic test, shortcut, language, try it.
"""
from __future__ import annotations

import grp
import os
import subprocess
import sys
import tempfile
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk, GLib  # noqa: E402

from freeflow.config import CONFIG_DIR, load
from freeflow.gui.state import GuiContext

ONBOARDED_PATH = CONFIG_DIR / ".onboarded"

SHORTCUT_PRESETS = [
    ("Ctrl + Alt + Shift (hold)", "KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFTSHIFT"),
    ("Ctrl + Space (hold)", "KEY_LEFTCTRL,KEY_SPACE"),
    ("Super + Space (hold)", "KEY_LEFTMETA,KEY_SPACE"),
]

LANGUAGES = [
    ("English (auto)", "auto"),
    ("English", "en"),
    ("Español", "es"),
    ("Français", "fr"),
]

TRY_IT_TEXT = "um can you uh send the file"

MIC_TEST_MIN_BYTES = 8192


def user_in_input_group() -> bool:
    """True if the current process's groups include 'input' (uinput access)."""
    try:
        input_gid = grp.getgrnam("input").gr_gid
    except KeyError:
        return False
    return input_gid in os.getgroups()


def ydotool_socket_present() -> bool:
    socket_path = os.environ.get("YDOTOOL_SOCKET", "/run/ydotoold.socket")
    return os.path.exists(socket_path)


def record_mic_sample(path: str, duration: int = 2) -> None:
    """Record `duration` seconds of audio to `path` via pw-record."""
    subprocess.run(
        ["timeout", str(duration), "pw-record", path],
        check=False,
        capture_output=True,
    )


def mic_test_passed(duration: int = 2) -> bool:
    """Record a short sample and report whether it looks non-trivial."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        record_mic_sample(path, duration)
        return os.path.getsize(path) > MIC_TEST_MIN_BYTES
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _permission_row(ok: bool, text: str) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    icon = Gtk.Label(label="✅" if ok else "❌")
    if not ok:
        icon.add_css_class("ff-danger")
    row.append(icon)
    row.append(Gtk.Label(label=text))
    return row


class OnboardingWindow(Gtk.ApplicationWindow):
    STEP_NAMES = ["permissions", "mic", "shortcut", "language", "tryit"]

    def __init__(self, application, ctx: GuiContext):
        super().__init__(application=application, title="Welcome to Freeflow")
        self.ctx = ctx
        self.set_default_size(560, 460)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(outer, m)(16)
        self.set_child(outer)

        self.stack = Gtk.Stack()
        outer.append(self.stack)

        self._shortcut_buttons: dict[str, Gtk.Button] = {}
        self._language_buttons: dict[str, Gtk.Button] = {}

        self.stack.add_named(self._build_permissions_step(), "permissions")
        self.stack.add_named(self._build_mic_step(), "mic")
        self.stack.add_named(self._build_shortcut_step(), "shortcut")
        self.stack.add_named(self._build_language_step(), "language")
        self.stack.add_named(self._build_tryit_step(), "tryit")
        self.stack.set_visible_child_name("permissions")

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        nav.set_halign(Gtk.Align.CENTER)
        self.prev_btn = Gtk.Button(label="← Prev")
        self.prev_btn.connect("clicked", self._on_prev)
        self.next_btn = Gtk.Button(label="Next →")
        self.next_btn.add_css_class("ff-pill-active")
        self.next_btn.connect("clicked", self._on_next)
        nav.append(self.prev_btn)
        nav.append(self.next_btn)
        outer.append(nav)
        self._update_nav()

    # ---------- navigation ----------

    def _current_index(self) -> int:
        return self.STEP_NAMES.index(self.stack.get_visible_child_name())

    def _update_nav(self) -> None:
        idx = self._current_index()
        self.prev_btn.set_sensitive(idx > 0)
        self.next_btn.set_label("Finish" if idx == len(self.STEP_NAMES) - 1 else "Next →")

    def _on_prev(self, _btn) -> None:
        idx = self._current_index()
        if idx > 0:
            self.stack.set_visible_child_name(self.STEP_NAMES[idx - 1])
            self._update_nav()

    def _on_next(self, _btn) -> None:
        idx = self._current_index()
        if idx < len(self.STEP_NAMES) - 1:
            self.stack.set_visible_child_name(self.STEP_NAMES[idx + 1])
            self._update_nav()
        else:
            self._finish()

    def _finish(self) -> None:
        ONBOARDED_PATH.parent.mkdir(parents=True, exist_ok=True)
        ONBOARDED_PATH.touch()
        self.close()

    # ---------- step 1: permissions ----------

    def _build_permissions_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title = Gtk.Label(label="Permissions")
        title.add_css_class("ff-serif")
        box.append(title)

        desc = Gtk.Label(
            label="Freeflow needs input-device and accessibility access to type on your behalf."
        )
        desc.add_css_class("ff-muted")
        box.append(desc)

        box.append(_permission_row(user_in_input_group(), "In 'input' group (uinput access)"))
        box.append(_permission_row(ydotool_socket_present(), "ydotool socket present"))

        hint = Gtk.Label(label="You may need to log out and back in for changes to take effect.")
        hint.add_css_class("ff-muted")
        box.append(hint)
        return box

    # ---------- step 2: mic test ----------

    def _build_mic_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title = Gtk.Label(label="Mic test")
        title.add_css_class("ff-serif")
        box.append(title)

        desc = Gtk.Label(label="Say something — we'll check the sample looks real.")
        desc.add_css_class("ff-muted")
        box.append(desc)

        result = Gtk.Label(label="")
        record_btn = Gtk.Button(label="Record 2s")
        record_btn.add_css_class("ff-pill-active")

        def on_record(_btn) -> None:
            record_btn.set_sensitive(False)

            def worker() -> None:
                passed = mic_test_passed()

                def report() -> None:
                    result.set_label("✅ mic looks good" if passed else "❌ no audio captured")
                    record_btn.set_sensitive(True)

                GLib.idle_add(report)

            threading.Thread(target=worker, daemon=True).start()

        record_btn.connect("clicked", on_record)
        box.append(record_btn)
        box.append(result)
        self._record_btn = record_btn
        self._mic_result = result
        return box

    # ---------- step 3: shortcut ----------

    def _build_shortcut_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title = Gtk.Label(label="Pick your shortcut")
        title.add_css_class("ff-serif")
        box.append(title)

        desc = Gtk.Label(label="Hold this combo anywhere to dictate.")
        desc.add_css_class("ff-muted")
        box.append(desc)

        pills = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.append(pills)

        def refresh() -> None:
            for keys, btn in self._shortcut_buttons.items():
                btn.remove_css_class("ff-pill-active")
                btn.remove_css_class("ff-pill")
                btn.add_css_class("ff-pill-active" if keys == self.ctx.cfg.keys else "ff-pill")

        for label, keys in SHORTCUT_PRESETS:
            btn = Gtk.Button(label=label)

            def on_click(_b, keys=keys) -> None:
                self.ctx.save(keys=keys)
                refresh()

            btn.connect("clicked", on_click)
            self._shortcut_buttons[keys] = btn
            pills.append(btn)

        refresh()
        return box

    # ---------- step 4: language ----------

    def _build_language_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title = Gtk.Label(label="Language")
        title.add_css_class("ff-serif")
        box.append(title)

        desc = Gtk.Label(label="Freeflow auto-detects your language, or you can pin one.")
        desc.add_css_class("ff-muted")
        box.append(desc)

        pills = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.append(pills)

        def refresh() -> None:
            for code, btn in self._language_buttons.items():
                btn.remove_css_class("ff-pill-active")
                btn.remove_css_class("ff-pill")
                btn.add_css_class("ff-pill-active" if code == self.ctx.cfg.language else "ff-pill")

        for label, code in LANGUAGES:
            btn = Gtk.Button(label=label)

            def on_click(_b, code=code) -> None:
                self.ctx.save(language=code)
                refresh()

            btn.connect("clicked", on_click)
            self._language_buttons[code] = btn
            pills.append(btn)

        refresh()
        return box

    # ---------- step 5: try it ----------

    def _build_tryit_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title = Gtk.Label(label="Try it")
        title.add_css_class("ff-serif")
        box.append(title)

        desc = Gtk.Label(label=f'Hold the keys and say: "{TRY_IT_TEXT}"')
        desc.add_css_class("ff-muted")
        box.append(desc)

        raw_entry = Gtk.Entry()
        raw_entry.set_text(TRY_IT_TEXT)
        box.append(raw_entry)

        result = Gtk.Label(label="")
        result.add_css_class("ff-pill-active")

        run_btn = Gtk.Button(label="Simulate dictation")
        run_btn.add_css_class("ff-pill-active")

        def on_run(_btn) -> None:
            text = raw_entry.get_text()
            cfg = self.ctx.cfg

            def worker() -> None:
                from freeflow import engine as engine_mod

                try:
                    cleaned, _press_enter = engine_mod.Engine(cfg).process(text)
                except Exception as exc:
                    GLib.idle_add(result.set_label, f"Couldn't run the engine: {exc}")
                    return
                GLib.idle_add(result.set_label, cleaned)

            threading.Thread(target=worker, daemon=True).start()

        run_btn.connect("clicked", on_run)
        box.append(run_btn)
        box.append(result)

        self._tryit_run_btn = run_btn
        self._tryit_result = result
        return box


def main(argv=None) -> int:
    # ponytail: NON_UNIQUE — this is a short-lived, one-shot wizard. With the
    # default unique/D-Bus-activated GApplication, a second `freeflow onboarding`
    # invocation doesn't open its own window: it re-activates whatever instance
    # is still registered (e.g. a background process left over from an earlier
    # run), which may already be sitting on a later step. That's the real cause
    # behind the wizard appearing to "open on Mic test" instead of Permissions.
    app = Gtk.Application(
        application_id="io.github.joshazmy.freeflow.onboarding",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    def on_activate(app) -> None:
        from freeflow.gui.style import apply_style
        apply_style()
        cfg = load()
        ctx = GuiContext(cfg=cfg)
        win = OnboardingWindow(application=app, ctx=ctx)
        win.present()

    app.connect("activate", on_activate)
    return app.run([sys.argv[0]] if argv is None else argv[:1])
