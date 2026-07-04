"""Freeflow CLI. Subcommands import their heavy deps lazily so `freeflow version`
works even without evdev/gi installed."""
import argparse
import os
import subprocess
import sys
import urllib.request

from freeflow import __version__
from freeflow.config import load, save_default


def cmd_run(args):
    from freeflow.engine import Engine
    Engine(load()).run()


def _http_reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def _ollama_has_model(base_url: str, model: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout) as r:
            import json
            data = json.loads(r.read())
        names = [m.get("name", "") for m in data.get("models", [])]
        return any(n == model or n.startswith(model.split(":")[0]) for n in names)
    except Exception:
        return False


def _systemd_active(unit: str) -> bool:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", unit],
                            capture_output=True, text=True, timeout=2)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def cmd_status(args):
    cfg = load()
    ok = True

    from freeflow.config import CONFIG_DIR
    print(f"config: {CONFIG_DIR / 'config.toml'}")

    server_up = bool(cfg.server) and _http_reachable(f"http://{cfg.server}/")
    print(f"{'✅' if server_up else '❌'} whisper-server ({cfg.server or 'disabled'}) reachable")

    bin_ok = bool(cfg.whisper_bin) and os.path.exists(cfg.whisper_bin)
    print(f"{'✅' if bin_ok else '❌'} whisper_bin exists ({cfg.whisper_bin or 'unset'})")

    model_ok = bool(cfg.model_path) and os.path.exists(cfg.model_path)
    print(f"{'✅' if model_ok else '❌'} model_path exists ({cfg.model_path or 'unset'})")

    # critical: need the server OR the cli+model fallback path
    if not (server_up or (bin_ok and model_ok)):
        ok = False

    ollama_up = _http_reachable(f"{cfg.ollama_url}/api/tags")
    print(f"{'✅' if ollama_up else '⚠️ '} ollama reachable ({cfg.ollama_url})")
    if ollama_up:
        model_present = _ollama_has_model(cfg.ollama_url, cfg.ollama_model)
        print(f"{'✅' if model_present else '⚠️ '} ollama model present ({cfg.ollama_model})")
    # ollama down/missing is a warning only -- cleanup degrades gracefully

    socket = os.environ.get("YDOTOOL_SOCKET", "/run/ydotoold.socket")
    socket_ok = os.path.exists(socket)
    print(f"{'✅' if socket_ok else '❌'} ydotool socket ({socket})")
    if not socket_ok:
        ok = False

    unit_active = _systemd_active("freeflow")
    print(f"{'✅' if unit_active else '⚠️ '} systemd unit freeflow active")

    return 0 if ok else 1


def cmd_config(args):
    if args.init:
        from freeflow.config import CONFIG_DIR
        path = save_default(str(CONFIG_DIR / "config.toml"))
        print(f"wrote default config to {path}")
        return 0
    cfg = load()
    for k, v in vars(cfg).items():
        print(f"{k} = {v!r}")
    return 0


def cmd_dictionary(args):
    from freeflow.dictionary import Dictionary
    cfg = load()
    d = Dictionary(cfg.dictionary_path)
    if args.action == "add":
        d.add(args.entry)
    elif args.action == "remove":
        d.remove(args.entry)
    elif args.action == "list":
        for w in d.words:
            print(w)
    return 0


def cmd_test(args):
    try:
        from freeflow.engine import Engine
    except ImportError as e:
        print(f"could not import engine (missing deps?): {e}", file=sys.stderr)
        return 1
    cfg = load()
    engine = Engine(cfg)
    result = engine.process(args.text)
    print(result)
    return 0


def cmd_version(args):
    print(__version__)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="freeflow")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("run").set_defaults(func=cmd_run)

    sub.add_parser("status").set_defaults(func=cmd_status)

    p_config = sub.add_parser("config")
    p_config.add_argument("--init", action="store_true")
    p_config.set_defaults(func=cmd_config)

    p_dict = sub.add_parser("dictionary")
    p_dict.add_argument("action", choices=["add", "remove", "list"])
    p_dict.add_argument("entry", nargs="?", default="")
    p_dict.set_defaults(func=cmd_dictionary)

    p_test = sub.add_parser("test")
    p_test.add_argument("text")
    p_test.set_defaults(func=cmd_test)

    sub.add_parser("version").set_defaults(func=cmd_version)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    ret = args.func(args)
    sys.exit(ret or 0)


if __name__ == "__main__":
    main()
