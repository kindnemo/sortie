import sys
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

from sortie.core.content_classifier import clip_model


@pytest.fixture(autouse=True)
def reset_clip_model_state():
    clip_model._model = None
    clip_model._preprocess = None
    clip_model._tokenizer = None
    clip_model._load_failed = False
    yield
    clip_model._model = None
    clip_model._preprocess = None
    clip_model._tokenizer = None
    clip_model._load_failed = False


def fake_open_clip(monkeypatch, *, fail_tokenizer=False):
    calls = {"create": [], "eval": 0, "tokenizer": []}
    preprocess = object()
    tokenizer = object()

    class FakeModel:
        def eval(self):
            calls["eval"] += 1

    model = FakeModel()

    def create_model_and_transforms(name, *, pretrained):
        calls["create"].append((name, pretrained))
        return model, object(), preprocess

    def get_tokenizer(name):
        calls["tokenizer"].append(name)
        if fail_tokenizer:
            raise RuntimeError("tokenizer unavailable")
        return tokenizer

    open_clip = ModuleType("open_clip")
    open_clip.create_model_and_transforms = create_model_and_transforms
    open_clip.get_tokenizer = get_tokenizer
    monkeypatch.setitem(sys.modules, "open_clip", open_clip)
    return calls, model, preprocess, tokenizer


def test_load_clip_loads_model_and_caches_components(monkeypatch):
    calls, model, preprocess, tokenizer = fake_open_clip(monkeypatch)

    assert clip_model._model is None
    assert calls["create"] == []  # Importing the module does not load CLIP.

    assert clip_model.load_clip() is True

    assert clip_model._model is model
    assert clip_model._preprocess is preprocess
    assert clip_model._tokenizer is tokenizer
    assert calls == {
        "create": [(clip_model.MODEL_NAME, clip_model.PRETRAINED)],
        "eval": 1,
        "tokenizer": [clip_model.MODEL_NAME],
    }

    # The expensive model creation and setup happen only once per process.
    assert clip_model.load_clip() is True
    assert calls["create"] == [(clip_model.MODEL_NAME, clip_model.PRETRAINED)]
    assert calls["eval"] == 1
    assert calls["tokenizer"] == [clip_model.MODEL_NAME]


def test_load_clip_caches_failure_without_retrying(monkeypatch):
    calls, _, _, _ = fake_open_clip(monkeypatch, fail_tokenizer=True)

    assert clip_model.load_clip() is False
    assert clip_model._load_failed is True
    assert clip_model._model is None

    # A failed load is also remembered, avoiding repeated expensive attempts.
    assert clip_model.load_clip() is False
    assert len(calls["create"]) == 1
    assert calls["eval"] == 1
    assert calls["tokenizer"] == [clip_model.MODEL_NAME]


def test_backend_ensure_loaded():
    image_path = Path(__file__).parent / "desert.jpg"
    assert image_path.exists(), f"Test image {image_path} does not exist."
    assert clip_model.backend.ensure_loaded() is True
    assert clip_model.backend.is_loaded() is True
    assert clip_model.backend.encode_texts(["a photo of a desert", "a meme"]).shape == (2, 512)
    with Image.open(image_path) as image:
        image_embedding = clip_model.backend.encode_image(image)
    assert image_embedding.shape == (512,)

