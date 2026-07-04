"""GuiContext: the shared state object every settings pane binds to.
Pure logic — no GTK needed."""
from freeflow.config import load, save_default
from freeflow.gui.state import GuiContext


def _ctx(tmp_path):
    cfg_path = tmp_path / "config.toml"
    save_default(str(cfg_path))
    dict_path = tmp_path / "dictionary.txt"
    cfg = load(str(cfg_path))
    cfg.dictionary_path = str(dict_path)
    return GuiContext(cfg=cfg, config_path=str(cfg_path))


def test_save_updates_cfg_file_and_flags_restart(tmp_path):
    ctx = _ctx(tmp_path)
    events = []
    ctx.on_restart_needed = lambda: events.append(1)

    ctx.save(language="auto", cleanup=False)

    assert ctx.cfg.language == "auto"          # in-memory cfg updated
    assert ctx.cfg.cleanup is False
    assert load(ctx.config_path).language == "auto"   # persisted
    assert ctx.restart_needed is True
    assert events == [1]

    ctx.save(threads=4)                        # hook fires once per save
    assert events == [1, 1]


def test_save_tone_overrides_roundtrip(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.save(tone_overrides={"discord": "casual"})
    assert load(ctx.config_path).tone_overrides == {"discord": "casual"}
    assert ctx.cfg.tone_overrides == {"discord": "casual"}


def test_dictionary_is_cached_and_live(tmp_path):
    ctx = _ctx(tmp_path)
    d = ctx.dictionary
    assert d is ctx.dictionary                 # same instance
    d.add("hyperland->Hyprland")
    assert "Hyprland" in ctx.dictionary.words
