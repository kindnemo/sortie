from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sortie.services import watcher


@pytest.fixture
def watch_directory(tmp_path):
    return tmp_path / "watch"


@pytest.fixture(autouse=True)
def isolated_movelog_db(tmp_path, monkeypatch):
    db_file = tmp_path / "movelog.db"
    monkeypatch.setattr(watcher.movelog, "data_path", lambda filename: db_file)
    return db_file


# ---------- FileClassifier ----------

def test_unique_destination_returns_original_when_available(tmp_path):
    destination = tmp_path / "report.txt"

    assert watcher.FileClassifier.unique_destination(destination) == destination


def test_unique_destination_adds_next_available_suffix(tmp_path):
    destination = tmp_path / "report.txt"
    destination.write_text("original")
    (tmp_path / "report(1).txt").write_text("first copy")

    assert watcher.FileClassifier.unique_destination(destination) == tmp_path / "report(2).txt"


def test_classify_file_moves_known_extension_to_category(watch_directory, tmp_path):
    source = tmp_path / "photo.JPG"
    source.write_text("image data")

    result = watcher.FileClassifier(watch_directory).classify_file(source)

    assert result == watch_directory / "Images" / "photo.JPG"
    assert result.read_text() == "image data"
    assert not source.exists()


def test_classify_file_uses_others_for_unknown_extension(watch_directory, tmp_path):
    source = tmp_path / "data.custom"
    source.write_text("content")

    result = watcher.FileClassifier(watch_directory).classify_file(source)

    assert result == watch_directory / "Others" / "data.custom"
    assert result.exists()


def test_classify_file_avoids_overwriting_existing_file(watch_directory, tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("new")
    existing = watch_directory / "Documents" / "report.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("old")

    result = watcher.FileClassifier(watch_directory).classify_file(source)

    assert result == watch_directory / "Documents" / "report(1).txt"
    assert existing.read_text() == "old"
    assert result.read_text() == "new"


def test_classify_file_does_not_move_file_already_in_destination(watch_directory):
    source = watch_directory / "Documents" / "report.txt"
    source.parent.mkdir(parents=True)
    source.write_text("content")

    result = watcher.FileClassifier(watch_directory).classify_file(source)

    assert result is None
    assert source.exists()


# ---------- Handler ----------

@pytest.mark.parametrize("name", ["partial.tmp", "download.crdownload"])
def test_handler_ignores_temporary_files(watch_directory, monkeypatch, name):
    watch_directory.mkdir()
    source = watch_directory / name
    source.write_text("content")
    wait_for_completion = Mock(return_value=True)
    monkeypatch.setattr(watcher, "wait_for_file_completion", wait_for_completion)

    watcher.Handler(watch_directory).handle_files(source)

    wait_for_completion.assert_not_called()
    assert source.exists()


def test_handler_ignores_files_already_in_category(watch_directory, monkeypatch):
    source = watch_directory / "Images" / "photo.jpg"
    source.parent.mkdir(parents=True)
    source.write_text("content")
    wait_for_completion = Mock(return_value=True)
    monkeypatch.setattr(watcher, "wait_for_file_completion", wait_for_completion)

    watcher.Handler(watch_directory).handle_files(source)

    wait_for_completion.assert_not_called()


def test_handler_processes_file_in_watch_root(tmp_path, monkeypatch):
    source = tmp_path / "a.jpg"
    source.write_text("image data")
    wait_for_completion = Mock(return_value=True)
    monkeypatch.setattr(watcher, "wait_for_file_completion", wait_for_completion)
    monkeypatch.setattr(watcher, "compute_file_hash", lambda _: "file-hash")
    monkeypatch.setattr(watcher.movelog, "find_duplicate", lambda _: False)
    monkeypatch.setattr(watcher.movelog, "log_move", Mock())

    watcher.Handler(tmp_path).handle_files(source)

    wait_for_completion.assert_called_once_with(source)
    assert (tmp_path / "Images" / "a.jpg").exists()


def test_handler_rejects_file_in_nested_subfolder(tmp_path, monkeypatch):
    source = tmp_path / "Images" / "GIFs" / "a.gif"
    source.parent.mkdir(parents=True)
    source.write_text("gif data")
    wait_for_completion = Mock(return_value=True)
    monkeypatch.setattr(watcher, "wait_for_file_completion", wait_for_completion)

    watcher.Handler(tmp_path).handle_files(source)

    wait_for_completion.assert_not_called()
    assert source.exists()


def test_handler_stops_when_file_is_not_complete(watch_directory, monkeypatch):
    watch_directory.mkdir()
    source = watch_directory / "report.txt"
    source.write_text("content")
    wait_for_completion = Mock(return_value=False)
    monkeypatch.setattr(watcher, "wait_for_file_completion", wait_for_completion)
    classify_file = Mock()
    monkeypatch.setattr(watcher.FileClassifier, "classify_file", classify_file)

    watcher.Handler(watch_directory).handle_files(source)

    wait_for_completion.assert_called_once_with(source)
    classify_file.assert_not_called()
    assert source.exists()


def test_handler_moves_file_and_logs_hash(watch_directory, monkeypatch):
    watch_directory.mkdir()
    source = watch_directory / "report.txt"
    source.write_text("content")
    monkeypatch.setattr(watcher, "wait_for_file_completion", lambda _: True)
    monkeypatch.setattr(watcher, "compute_file_hash", lambda _: "file-hash")
    monkeypatch.setattr(watcher.movelog, "find_duplicate", lambda _: False)
    log_move = Mock()
    monkeypatch.setattr(watcher.movelog, "log_move", log_move)

    watcher.Handler(watch_directory).handle_files(source)

    destination = watch_directory / "Documents" / "report.txt"
    assert destination.exists()
    log_move.assert_called_once_with(
        source_path=str(source),
        dest_path=str(destination),
        chain=["Documents"],
        confidence=None,
        needs_review=False,
        file_hash="file-hash",
    )


def test_handler_sends_duplicate_to_duplicates_folder(watch_directory, monkeypatch):
    watch_directory.mkdir()
    source = watch_directory / "report.txt"
    source.write_text("content")
    monkeypatch.setattr(watcher, "wait_for_file_completion", lambda _: True)
    monkeypatch.setattr(watcher, "compute_file_hash", lambda _: "known-hash")
    monkeypatch.setattr(watcher.movelog, "find_duplicate", lambda _: True)
    monkeypatch.setattr(watcher.movelog, "log_move", Mock())

    watcher.Handler(watch_directory).handle_files(source)

    assert (watch_directory / "Duplicates" / "report.txt").exists()


@pytest.mark.parametrize(
    ("method", "attribute"),
    [("on_created", "src_path"), ("on_moved", "dest_path")],
)
def test_event_methods_pass_file_path_to_handler(watch_directory, method, attribute, monkeypatch):
    handler = watcher.Handler(watch_directory)
    handle_files = Mock()
    monkeypatch.setattr(handler, "handle_files", handle_files)
    event = SimpleNamespace(is_directory=False, **{attribute: "C:/incoming/report.txt"})

    getattr(handler, method)(event)

    handle_files.assert_called_once_with(Path("C:/incoming/report.txt"))


def test_event_methods_ignore_directories(watch_directory, monkeypatch):
    handler = watcher.Handler(watch_directory)
    handle_files = Mock()
    monkeypatch.setattr(handler, "handle_files", handle_files)
    event = SimpleNamespace(is_directory=True, src_path="ignored", dest_path="ignored")

    handler.on_created(event)
    handler.on_moved(event)

    handle_files.assert_not_called()


# ---------- Configuration and entry point ----------

def test_resolve_watch_directory_prefers_command_line_value(monkeypatch):
    get_saved_directory = Mock(return_value=Path("saved"))
    monkeypatch.setattr(watcher, "settings", SimpleNamespace(get_watch_directory=get_saved_directory))

    folder, source = watcher.resolve_watch_directory("from-cli")

    assert folder == Path("from-cli")
    assert source == "command line"
    get_saved_directory.assert_not_called()


def test_resolve_watch_directory_uses_saved_setting(monkeypatch):
    saved = Path("saved-folder")
    monkeypatch.setattr(watcher, "settings", SimpleNamespace(get_watch_directory=lambda: saved))

    assert watcher.resolve_watch_directory(None) == (saved, "saved settings")


def test_resolve_watch_directory_uses_default_without_settings(monkeypatch, tmp_path):
    default = tmp_path / "default"
    monkeypatch.setattr(watcher.settings, "get_watch_directory", lambda: None)
    monkeypatch.setattr(watcher, "WATCH_DIRECTORY", default)

    assert watcher.resolve_watch_directory(None) == (default, "dev default")


def test_main_starts_watcher_for_existing_cli_directory(tmp_path, monkeypatch, capsys):
    started_with = []

    class FakeWatch:
        def __init__(self, folder):
            started_with.append(folder)

        def run(self):
            pass

    monkeypatch.setattr(watcher, "OnMyWatch", FakeWatch)

    assert watcher.main([str(tmp_path)]) == 0
    assert started_with == [tmp_path]
    assert f"Watching {tmp_path} (from command line)" in capsys.readouterr().out


def test_main_rejects_missing_cli_directory(tmp_path, capsys):
    missing = tmp_path / "missing"

    assert watcher.main([str(missing)]) == 1
    assert "Watch folder not found" in capsys.readouterr().out
