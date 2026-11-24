"""
User settings for Sortie, stored as JSON in the app data folder.

This module owns two things:
  1. Reading and writing settings.json safely.
  2. Deciding what counts as a valid watch folder.

The watcher and the future GUI both go through these functions, so the rules
live in exactly one place.
"""

import json
import os
import tempfile
from pathlib import Path

from sortie.core.extension_classifier.extension_map import EXT_MAP
from sortie.paths import data_dir, data_path

SETTINGS_FILENAME = "settings.json"
SETTINGS_VERSION = 1

DEFAULTS = {
    "version": SETTINGS_VERSION,
    "watch_directory": None,
}

# Folder names the sorter itself creates. Watching one of these would do
# nothing, because the handler ignores files whose parent is a category folder.
# Lowercased because Windows paths are case-insensitive.
CATEGORY_NAMES = {name.lower() for name in set(EXT_MAP.values()) | {"Others", "Duplicates"}}

# Environment variables that point at Windows system locations.
_SYSTEM_ENV_VARS = ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")



def load_settings() -> dict:
    """
    Read settings.json and return it merged over the defaults.

    A missing, unreadable or corrupt file is not an error: the defaults are
    returned instead, so a half-written file can never stop the app starting.

    Returns:
        dict: the settings, always containing every key in DEFAULTS.
    """
    settings = dict(DEFAULTS)

    try:
        with open(data_path(SETTINGS_FILENAME), "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except (OSError, ValueError):
        # OSError covers missing/locked files; ValueError covers bad JSON
        # and bad encoding.
        return settings

    if isinstance(loaded, dict):
        settings.update(loaded)
    return settings


def save_settings(settings: dict) -> None:
    """
    Write settings to settings.json atomically.

    The data goes to a temp file in the same folder first and is then swapped
    over the real file, so a crash mid-write can't leave a half-written file.

    Args:
        settings (dict): the full settings dict to store.
    Returns:
        None
    """
    path = data_path(SETTINGS_FILENAME)

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix="settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise



def _same_path(a: Path, b: Path) -> bool:
    """Compare two paths the way Windows does (case and slash insensitive)."""
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def _is_inside(path: Path, parent: Path) -> bool:
    """True if path is parent itself or anywhere below it."""
    return _same_path(path, parent) or any(_same_path(p, parent) for p in path.parents)


def _validate_watch_directory(raw) -> Path:
    """
    Check a candidate watch folder, creating it if needed.

    Args:
        raw (str or Path): the folder the user chose.
    Returns:
        Path: the cleaned, absolute, resolved folder.
    Raises:
        ValueError: with a message safe to show directly to the user.
    """
    # 1. Basic shape
    if not isinstance(raw, (str, Path)) or not str(raw).strip():
        raise ValueError("Please choose a folder.")

    # 2. Normalise to one canonical absolute path
    path = Path(str(raw).strip()).expanduser()
    if not path.is_absolute():
        raise ValueError("Please give the full path to the folder, including the drive.")
    path = path.resolve()

    # 3. Too broad: a misclick here would make Sortie sort a whole profile
    if _same_path(path, Path(path.anchor)):
        raise ValueError("That is a whole drive. Choose a folder inside it instead.")
    if _same_path(path, Path.home()):
        raise ValueError("That is your whole user folder. Choose a subfolder, such as Downloads.")
    for var in _SYSTEM_ENV_VARS:
        system_dir = os.environ.get(var)
        if system_dir and _is_inside(path, Path(system_dir)):
            raise ValueError("That is a system folder. Choose a different folder.")

    # 4. Sortie's own data folder
    if _is_inside(path, data_dir()):
        raise ValueError("That folder is used by Sortie to store its own data. Choose a different one.")

    # 5. A category folder the sorter creates itself
    if path.name.lower() in CATEGORY_NAMES:
        raise ValueError(
            f"'{path.name}' is one of Sortie's category folders. "
            "Choose the folder that contains it instead."
        )

    # 6. Must be a folder, not a file
    if path.exists() and not path.is_dir():
        raise ValueError("That path is a file, not a folder.")

    # 7. Create it if missing
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"Could not create that folder: {e}") from e

    # 8. Must be writable: the mover creates category folders inside it.
    #    A real create-and-delete is more reliable than os.access on Windows.
    try:
        with tempfile.TemporaryFile(dir=path):
            pass
    except OSError as e:
        raise ValueError(f"Sortie can't write to that folder: {e}") from e

    return path




def get_watch_directory():
    """
    Return the saved watch folder, or None if none has been set.

    The folder is not re-validated here. If it was deleted after saving, the
    watcher's startup check reports it.

    Returns:
        Path or None
    """
    value = load_settings().get("watch_directory")
    if not isinstance(value, str) or not value:
        return None
    return Path(value)


def set_watch_directory(raw) -> Path:
    """
    Validate a folder, create it if needed, and save it as the watch folder.

    Other keys already in settings.json are preserved.

    Args:
        raw (str or Path): the folder the user chose.
    Returns:
        Path: the cleaned folder that was saved.
    Raises:
        ValueError: if the folder isn't acceptable; nothing is saved.
    """
    path = _validate_watch_directory(raw)

    settings = load_settings()
    settings["watch_directory"] = str(path)
    settings["version"] = SETTINGS_VERSION
    save_settings(settings)

    return path

