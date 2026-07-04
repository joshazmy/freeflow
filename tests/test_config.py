import os

from freeflow.config import Config, load, save_default


def test_load_missing_file_gives_defaults(tmp_path):
    cfg = load(str(tmp_path / "does-not-exist.toml"))
    assert cfg == Config()


def test_load_missing_keys_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('language = "fr"\n')
    cfg = load(str(path))
    assert cfg.language == "fr"
    assert cfg.threads == 8  # default, key was absent


def test_env_override_wins_over_file(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text('threads = 4\n')
    monkeypatch.setenv("FREEFLOW_THREADS", "16")
    cfg = load(str(path))
    assert cfg.threads == 16


def test_env_override_parses_bool(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEFLOW_CLEANUP", "false")
    cfg = load(str(tmp_path / "nope.toml"))
    assert cfg.cleanup is False


def test_history_defaults_true(tmp_path):
    cfg = load(str(tmp_path / "nope.toml"))
    assert cfg.history is True


def test_history_toml_override(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("history = false\n")
    cfg = load(str(path))
    assert cfg.history is False


def test_history_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEFLOW_HISTORY", "false")
    cfg = load(str(tmp_path / "nope.toml"))
    assert cfg.history is False


def test_env_override_parses_float(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEFLOW_CLEANUP_TIMEOUT", "2.5")
    cfg = load(str(tmp_path / "nope.toml"))
    assert cfg.cleanup_timeout == 2.5


def test_tone_overrides_not_env_overridable(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEFLOW_TONE_OVERRIDES", "slack=casual")
    cfg = load(str(tmp_path / "nope.toml"))
    assert cfg.tone_overrides == {}


def test_save_default_writes_file_once(tmp_path):
    path = tmp_path / "cfg" / "config.toml"
    result = save_default(str(path))
    assert result == path
    assert path.exists()
    contents = path.read_text()
    assert "whisper_bin" in contents
    # second call must not clobber an edited file
    path.write_text("# edited by user\n")
    save_default(str(path))
    assert path.read_text() == "# edited by user\n"


# --- save_values (GUI write-back) ---

def test_save_values_updates_existing_key_and_keeps_comments(tmp_path):
    from freeflow.config import save_default, save_values, load
    p = tmp_path / "config.toml"
    save_default(str(p))
    save_values({"language": "auto", "cleanup": False, "threads": 4}, str(p))
    cfg = load(str(p))
    assert cfg.language == "auto"
    assert cfg.cleanup is False
    assert cfg.threads == 4
    text = p.read_text()
    assert "# Freeflow configuration" in text  # comments survive


def test_save_values_appends_missing_key(tmp_path):
    from freeflow.config import save_values, load
    p = tmp_path / "config.toml"
    p.write_text('language = "en"\n')
    save_values({"ollama_model": "qwen3:4b"}, str(p))
    assert load(str(p)).ollama_model == "qwen3:4b"


def test_save_values_tone_overrides(tmp_path):
    from freeflow.config import save_default, save_values, load
    p = tmp_path / "config.toml"
    save_default(str(p))
    save_values({"tone_overrides": {"slack": "casual", "thunderbird": "formal"}}, str(p))
    cfg = load(str(p))
    assert cfg.tone_overrides == {"slack": "casual", "thunderbird": "formal"}
    # replace, not merge: saving again with fewer entries drops the rest
    save_values({"tone_overrides": {"slack": "casual"}}, str(p))
    assert load(str(p)).tone_overrides == {"slack": "casual"}


def test_save_values_creates_file_when_missing(tmp_path):
    from freeflow.config import save_values, load
    p = tmp_path / "config.toml"
    save_values({"language": "auto"}, str(p))
    assert load(str(p)).language == "auto"


def test_save_values_preserves_foreign_sections_and_root_placement(tmp_path):
    from freeflow.config import save_values, load
    p = tmp_path / "config.toml"
    p.write_text('language = "en"\n\n[custom]\nfoo = "bar"\n\n[tone_overrides]\nslack = "casual"\n')
    save_values({"threads": 4, "tone_overrides": {"slack": "formal"}}, str(p))
    text = p.read_text()
    assert "[custom]" in text and 'foo = "bar"' in text     # foreign section survives
    cfg = load(str(p))
    assert cfg.threads == 4                                  # new key readable at root
    assert cfg.tone_overrides == {"slack": "formal"}
    import tomllib
    data = tomllib.loads(text)
    assert data["threads"] == 4                              # NOT inside [custom]


def test_save_values_escapes_control_chars(tmp_path):
    from freeflow.config import save_values, load
    p = tmp_path / "config.toml"
    save_values({"ollama_model": "bad\nname\tx"}, str(p))
    assert load(str(p)).ollama_model == "bad\nname\tx"       # file stays parseable


# --- dark mode field (round 3) ---

def test_dark_defaults_false(tmp_path):
    cfg = load(str(tmp_path / "nope.toml"))
    assert cfg.dark is False


def test_dark_toml_override(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("dark = true\n")
    cfg = load(str(path))
    assert cfg.dark is True


def test_dark_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEFLOW_DARK", "true")
    cfg = load(str(tmp_path / "nope.toml"))
    assert cfg.dark is True


def test_default_toml_has_commented_dark_line_before_tone_overrides(tmp_path):
    from freeflow.config import save_default
    p = tmp_path / "config.toml"
    save_default(str(p))
    text = p.read_text()
    assert "# dark = false" in text
    assert text.index("# dark = false") < text.index("[tone_overrides]")
    # commented out: loading the default file must not set dark=True
    assert load(str(p)).dark is False
