import json
from pathlib import Path

import pytest

from sortie.core import settings
from sortie.core.extension_classifier.extension_map import EXT_MAP


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    """
    Point settings.py at a throwaway data folder so tests never touch the
    real AppData. Both names are patched: data_path (where settings.json
    lives) and data_dir (used by the own-data-folder rule).
    """
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(settings, "data_dir", lambda: data)
    monkeypatch.setattr(settings, "data_path", lambda name: data / name)
    return data


def settings_file(app_data):
    return app_data / settings.SETTINGS_FILENAME


# ---------- load_settings ----------

def test_load_missing_file_returns_defaults(app_data):
    assert settings.load_settings() == settings.DEFAULTS


def test_load_returns_a_copy_not_the_defaults_themselves(app_data):
    first = settings.load_settings()
    first["watch_directory"] = "mutated"
    assert settings.load_settings()["watch_directory"] is None
    assert settings.DEFAULTS["watch_directory"] is None


def test_load_corrupt_json_returns_defaults(app_data):
    settings_file(app_data).write_text("{broken", encoding="utf-8")
    assert settings.load_settings() == settings.DEFAULTS


def test_load_non_dict_json_returns_defaults(app_data):
    settings_file(app_data).write_text("[1, 2, 3]", encoding="utf-8")
    assert settings.load_settings() == settings.DEFAULTS


def test_load_fills_in_missing_keys(app_data):
    settings_file(app_data).write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    loaded = settings.load_settings()
    assert loaded["theme"] == "dark"
    assert loaded["watch_directory"] is None
    assert loaded["version"] == settings.SETTINGS_VERSION


# ---------- save_settings ----------

def test_save_then_load_round_trip(app_data):
    data = {"version": 1, "watch_directory": "X:/somewhere", "theme": "dark"}
    settings.save_settings(data)
    assert settings.load_settings() == data


def test_save_leaves_no_temp_files_behind(app_data):
    settings.save_settings({"version": 1, "watch_directory": None})
    assert [p.name for p in app_data.iterdir()] == [settings.SETTINGS_FILENAME]


def test_failed_save_keeps_old_file_and_cleans_up(app_data, monkeypatch):
    settings.save_settings({"version": 1, "watch_directory": "old"})

    def boom(*args, **kwargs):
        raise OSError("disk exploded")

    monkeypatch.setattr(settings.os, "replace", boom)
    with pytest.raises(OSError):
        settings.save_settings({"version": 1, "watch_directory": "new"})
    monkeypatch.undo()

    # old content survives untouched, and the temp file was removed
    assert json.loads(settings_file(app_data).read_text(encoding="utf-8"))["watch_directory"] == "old"
    assert [p.name for p in app_data.iterdir()] == [settings.SETTINGS_FILENAME]


# ---------- get_watch_directory ----------

def test_get_returns_none_when_unset(app_data):
    assert settings.get_watch_directory() is None


def test_get_ignores_a_non_string_value(app_data):
    settings.save_settings({"version": 1, "watch_directory": 5})
    assert settings.get_watch_directory() is None


def test_get_ignores_an_empty_string(app_data):
    settings.save_settings({"version": 1, "watch_directory": ""})
    assert settings.get_watch_directory() is None


# ---------- set_watch_directory: the happy paths ----------

def test_set_then_get_returns_same_path(app_data, tmp_path):
    saved = settings.set_watch_directory(tmp_path / "watch")
    assert isinstance(saved, Path)
    assert settings.get_watch_directory() == saved


def test_set_creates_a_missing_nested_folder(app_data, tmp_path):
    target = tmp_path / "a" / "b" / "watch"
    assert not target.exists()
    settings.set_watch_directory(target)
    assert target.is_dir()


def test_set_accepts_str_and_path(app_data, tmp_path):
    from_str = settings.set_watch_directory(str(tmp_path / "one"))
    from_path = settings.set_watch_directory(tmp_path / "two")
    assert from_str.name == "one"
    assert from_path.name == "two"


def test_set_returns_a_resolved_absolute_path(app_data, tmp_path):
    messy = tmp_path / "x" / ".." / "watch"
    saved = settings.set_watch_directory(messy)
    assert saved.is_absolute()
    assert ".." not in saved.parts
    assert saved == (tmp_path / "watch").resolve()


def test_set_strips_surrounding_whitespace(app_data, tmp_path):
    saved = settings.set_watch_directory(f"  {tmp_path / 'watch'}  ")
    assert saved == (tmp_path / "watch").resolve()


def test_set_is_stored_as_a_string_in_the_file(app_data, tmp_path):
    saved = settings.set_watch_directory(tmp_path / "watch")
    on_disk = json.loads(settings_file(app_data).read_text(encoding="utf-8"))
    assert on_disk["watch_directory"] == str(saved)
    assert on_disk["version"] == settings.SETTINGS_VERSION


def test_set_preserves_other_keys(app_data, tmp_path):
    settings.save_settings({"version": 1, "watch_directory": None, "theme": "dark"})
    settings.set_watch_directory(tmp_path / "watch")
    assert settings.load_settings()["theme"] == "dark"


def test_set_replaces_the_previous_folder(app_data, tmp_path):
    settings.set_watch_directory(tmp_path / "first")
    second = settings.set_watch_directory(tmp_path / "second")
    assert settings.get_watch_directory() == second


def test_setting_the_same_existing_folder_twice_is_fine(app_data, tmp_path):
    first = settings.set_watch_directory(tmp_path / "watch")
    second = settings.set_watch_directory(tmp_path / "watch")
    assert first == second


# ---------- set_watch_directory: rejected input ----------

@pytest.mark.parametrize("bad", ["", "   ", None, 123, ["x"]])
def test_set_rejects_empty_or_wrong_type(app_data, bad):
    with pytest.raises(ValueError, match="choose a folder"):
        settings.set_watch_directory(bad)


def test_set_rejects_a_relative_path_and_creates_nothing(app_data, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="full path"):
        settings.set_watch_directory("some_relative_folder")
    assert not (tmp_path / "some_relative_folder").exists()


def test_set_rejects_a_drive_root(app_data, tmp_path):
    with pytest.raises(ValueError, match="whole drive"):
        settings.set_watch_directory(Path(tmp_path.anchor))


def test_set_rejects_the_home_folder(app_data, tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(settings.Path, "home", lambda: fake_home)
    with pytest.raises(ValueError, match="user folder"):
        settings.set_watch_directory(fake_home)


def test_set_allows_a_subfolder_of_home(app_data, tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(settings.Path, "home", lambda: fake_home)
    saved = settings.set_watch_directory(fake_home / "Downloads")
    assert saved.name == "Downloads"


def test_set_rejects_system_folders_and_their_children(app_data, tmp_path, monkeypatch):
    fake_windows = tmp_path / "fake_windows"
    fake_windows.mkdir()
    monkeypatch.setenv("SystemRoot", str(fake_windows))
    with pytest.raises(ValueError, match="system folder"):
        settings.set_watch_directory(fake_windows)
    with pytest.raises(ValueError, match="system folder"):
        settings.set_watch_directory(fake_windows / "Temp")


def test_set_rejects_the_apps_own_data_folder(app_data):
    with pytest.raises(ValueError, match="store its own data"):
        settings.set_watch_directory(app_data)


def test_set_rejects_a_folder_inside_the_apps_data_folder(app_data):
    with pytest.raises(ValueError, match="store its own data"):
        settings.set_watch_directory(app_data / "sub")
    assert not (app_data / "sub").exists()


def test_set_rejects_category_folder_names(app_data, tmp_path):
    some_category = next(iter(EXT_MAP.values()))
    for name in ("Duplicates", "Others", some_category):
        with pytest.raises(ValueError, match="category folders"):
            settings.set_watch_directory(tmp_path / name)
        assert not (tmp_path / name).exists()


def test_category_check_ignores_letter_case(app_data, tmp_path):
    with pytest.raises(ValueError, match="category folders"):
        settings.set_watch_directory(tmp_path / "DUPLICATES")


def test_set_rejects_a_file(app_data, tmp_path):
    a_file = tmp_path / "notes.txt"
    a_file.write_text("hi", encoding="utf-8")
    with pytest.raises(ValueError, match="file, not a folder"):
        settings.set_watch_directory(a_file)


def test_set_rejects_a_folder_that_cannot_be_created(app_data, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not create"):
        settings.set_watch_directory(blocker / "watch")


def test_set_rejects_a_folder_that_is_not_writable(app_data, tmp_path, monkeypatch):
    def deny(*args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr(settings.tempfile, "TemporaryFile", deny)
    with pytest.raises(ValueError, match="can't write"):
        settings.set_watch_directory(tmp_path / "watch")


# ---------- a rejected set must change nothing ----------

def test_rejected_set_does_not_save_anything(app_data, tmp_path):
    with pytest.raises(ValueError):
        settings.set_watch_directory(tmp_path / "Duplicates")
    assert not settings_file(app_data).exists()
    assert settings.get_watch_directory() is None


def test_rejected_set_keeps_the_previous_folder(app_data, tmp_path):
    good = settings.set_watch_directory(tmp_path / "watch")
    with pytest.raises(ValueError):
        settings.set_watch_directory(tmp_path / "Others")
    assert settings.get_watch_directory() == good