"""Settings window: sidebar ListBox + Gtk.Stack + restart banner."""
from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from freeflow.gui.panes import PANES


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, application, ctx, **kwargs):
        super().__init__(application=application, title="Freeflow Settings", **kwargs)
        self.ctx = ctx
        self.set_default_size(900, 600)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_child(root)

        # --- sidebar ---
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(200, -1)

        wordmark = Gtk.Label(label="Freeflow")
        wordmark.add_css_class("ff-serif")
        wordmark.add_css_class("ff-wordmark")
        wordmark.add_css_class("title-2")
        wordmark.set_margin_top(16)
        wordmark.set_margin_bottom(8)
        wordmark.set_margin_start(16)
        wordmark.set_xalign(0)
        sidebar_box.append(wordmark)

        self.sidebar = Gtk.ListBox()
        self.sidebar.add_css_class("ff-sidebar")
        self.sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        sidebar_box.append(self.sidebar)
        root.append(sidebar_box)

        # --- content: restart banner (revealer) + stack ---
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        root.append(content_box)

        self.restart_banner = Gtk.Revealer()
        self.restart_banner.set_reveal_child(False)
        banner_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        banner_bar.set_margin_top(8)
        banner_bar.set_margin_bottom(8)
        banner_bar.set_margin_start(12)
        banner_bar.set_margin_end(12)
        self.restart_label = Gtk.Label(
            label="Restart Freeflow to apply changes", hexpand=True, xalign=0
        )
        banner_bar.append(self.restart_label)
        self.restart_button = Gtk.Button(label="Restart now")
        self.restart_button.add_css_class("ff-pill-active")
        self.restart_button.connect("clicked", self._on_restart_now)
        banner_bar.append(self.restart_button)
        self.restart_banner.set_child(banner_bar)
        content_box.append(self.restart_banner)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        # scroll instead of clipping controls off-screen when the window is tiled small
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.stack)
        content_box.append(scroller)

        for pane_id, title, build in PANES:
            row = Gtk.ListBoxRow()
            row.set_child(Gtk.Label(label=title, xalign=0))
            row.pane_id = pane_id
            self.sidebar.append(row)
            self.stack.add_titled(build(ctx), pane_id, title)

        self.sidebar.connect("row-activated", self._on_row_activated)
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        self.stack.set_visible_child_name(PANES[0][0])

        ctx.on_restart_needed = self._show_restart_banner

    def _on_row_activated(self, listbox, row):
        self.stack.set_visible_child_name(row.pane_id)

    def _show_restart_banner(self) -> None:
        self.restart_banner.set_reveal_child(True)

    def _on_restart_now(self, button) -> None:
        try:
            result = subprocess.run(["systemctl", "--user", "restart", "freeflow"])
            ok = result.returncode == 0
        except Exception:
            ok = False

        if ok:
            self.ctx.restart_needed = False
            self.restart_banner.set_reveal_child(False)
        else:
            self.restart_label.set_label(
                "Restart failed — run: systemctl --user restart freeflow"
            )
