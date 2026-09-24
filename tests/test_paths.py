from pathlib import Path

import platformdirs
import pytest

from sortie import paths


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    root = tmp_path / "sortie_data"  # deliberately does not exist yet
    monkeypatch.setattr(
        platformdirs, "user_data_dir", lambda *args, **kwargs: str(root)
    )
    return root


# ---------- data_dir ----------

def test_data_dir_returns_path(fake_root):
    assert isinstance(paths.data_dir(), Path)


def test_data_dir_creates_folder(fake_root):
    assert not fake_root.exists()      # before
    result = paths.data_dir()
    assert result.is_dir()             # after


def test_data_dir_uses_platformdirs_location(fake_root):
    assert paths.data_dir() == fake_root


def test_data_dir_can_be_called_twice(fake_root):
    first = paths.data_dir()
    second = paths.data_dir()          # must not raise
    assert first == second


# ---------- data_path ----------

def test_data_path_name_and_parent(fake_root):
    result = paths.data_path("sortie.db")
    assert result.name == "sortie.db"
    assert result.parent == fake_root


def test_data_path_does_not_create_file(fake_root):
    result = paths.data_path("sortie.db")
    assert not result.exists()


# ---------- model_cache_dir ----------

def test_model_cache_dir(fake_root):
    result = paths.model_cache_dir()
    assert result.name == "models"
    assert result.parent == fake_root
    assert result.is_dir()


# ---------- real location (no fake) ----------

def test_real_data_dir_is_not_inside_repo():
    repo_root = Path(__file__).resolve().parents[1]
    assert not paths.data_dir().resolve().is_relative_to(repo_root)
    