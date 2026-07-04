"""Active-window detection and tone selection (Hyprland / Sway)."""
import json
import subprocess

from freeflow.config import Config

TIMEOUT = 1.0

# Built-in category maps (lower-cased app_class).
_EMAIL_APPS = {"thunderbird", "evolution", "betterbird"}
_WORK_CHAT_APPS = {"slack", "teams"}
_PERSONAL_CHAT_APPS = {"discord", "telegram", "signal", "whatsapp", "element"}
_EMAIL_TITLE_HINTS = ("gmail", "proton mail")


def _from_hyprctl() -> tuple[str, str] | None:
    try:
        out = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        data = json.loads(out.stdout)
    except ValueError:
        return None
    app_class = str(data.get("class", "") or "").lower()
    title = str(data.get("title", "") or "")
    if not app_class and not title:
        return None
    return app_class, title


def _walk_sway_tree(node: dict) -> tuple[str, str] | None:
    if node.get("focused"):
        app_class = node.get("app_id") or (node.get("window_properties") or {}).get("class") or ""
        title = node.get("name") or ""
        return str(app_class).lower(), str(title)
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = _walk_sway_tree(child)
        if found is not None:
            return found
    return None


def _from_swaymsg() -> tuple[str, str] | None:
    try:
        out = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        data = json.loads(out.stdout)
    except ValueError:
        return None
    return _walk_sway_tree(data)


def active_app() -> tuple[str, str]:
    """Return (app_class, window_title), lowercased class; ("", "") on failure."""
    for detector in (_from_hyprctl, _from_swaymsg):
        result = detector()
        if result is not None:
            return result
    return "", ""


def tone_for(app_class: str, title: str, cfg: Config) -> str:
    """Return "formal" | "casual" | "neutral" for the given window context."""
    app_class = (app_class or "").lower()
    title_lower = (title or "").lower()

    override = (cfg.tone_overrides or {}).get(app_class)
    if override:
        return override

    if app_class in _EMAIL_APPS or any(hint in title_lower for hint in _EMAIL_TITLE_HINTS):
        return "formal"
    if app_class in _WORK_CHAT_APPS:
        return "formal"
    if app_class in _PERSONAL_CHAT_APPS:
        return "casual"
    return "neutral"
