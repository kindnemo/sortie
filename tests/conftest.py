"""Shared pytest fixtures — auto-discovered by pytest, no import needed."""

import pytest
from PIL import Image

from sortie.core.content_classifier import image


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    """Wipe _text_cache before every test so cached vectors don't leak."""
    monkeypatch.setattr(image, "_text_cache", {})


@pytest.fixture
def sample_image(tmp_path):
    """Create a tiny real JPEG so Image.open() doesn't fail."""
    p = tmp_path / "x.jpg"
    Image.new("RGB", (8, 8)).save(p)
    return p
