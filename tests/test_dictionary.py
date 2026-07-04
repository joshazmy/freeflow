from freeflow.dictionary import Dictionary


def test_missing_file_is_empty(tmp_path):
    d = Dictionary(str(tmp_path / "nope.txt"))
    assert d.words == []
    assert d.apply("hello world") == "hello world"


def test_add_creates_parent_dir_and_persists(tmp_path):
    path = tmp_path / "sub" / "dictionary.txt"
    d = Dictionary(str(path))
    d.add("Hyprland")
    assert path.exists()

    d2 = Dictionary(str(path))
    assert "Hyprland" in d2.words


def test_add_wrong_arrow_right(tmp_path):
    path = tmp_path / "dictionary.txt"
    d = Dictionary(str(path))
    d.add("hyperland->Hyprland")
    assert d.apply("I use hyperland daily") == "I use Hyprland daily"


def test_plain_word_normalizes_case_variants(tmp_path):
    path = tmp_path / "dictionary.txt"
    d = Dictionary(str(path))
    d.add("Hyprland")
    assert d.apply("HYPRLAND is great, hyprland rocks") == "Hyprland is great, Hyprland rocks"


def test_apply_is_word_boundary_safe(tmp_path):
    path = tmp_path / "dictionary.txt"
    d = Dictionary(str(path))
    d.add("cat->Cat")
    assert d.apply("concatenate the cat") == "concatenate the Cat"


def test_apply_preserves_surrounding_punctuation(tmp_path):
    path = tmp_path / "dictionary.txt"
    d = Dictionary(str(path))
    d.add("hyperland->Hyprland")
    assert d.apply("(hyperland), hyperland!") == "(Hyprland), Hyprland!"


def test_remove_round_trip(tmp_path):
    path = tmp_path / "dictionary.txt"
    d = Dictionary(str(path))
    d.add("Hyprland")
    d.add("hyperland->Hyprland")
    assert "Hyprland" in d.words

    d.remove("hyperland->Hyprland")
    assert d.apply("hyperland") == "hyperland"
    assert d.apply("HYPRLAND") == "Hyprland"

    d2 = Dictionary(str(path))
    assert d2.apply("hyperland") == "hyperland"
    assert d2.apply("hyprland") == "Hyprland"


def test_comment_lines_ignored(tmp_path):
    path = tmp_path / "dictionary.txt"
    path.write_text("# a comment\nHyprland\n\n# another\nwispr->Wispr\n")
    d = Dictionary(str(path))
    assert set(d.words) == {"Hyprland", "Wispr"}


def test_list_returns_canonical_spellings(tmp_path):
    path = tmp_path / "dictionary.txt"
    d = Dictionary(str(path))
    d.add("Hyprland")
    d.add("wispr->Wispr")
    assert d.words == ["Hyprland", "Wispr"]
