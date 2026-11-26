import pytest
from PIL import Image
from types import SimpleNamespace as NS

from sortie.core.content_classifier import image
from sortie.core.content_classifier.dispatch import (
    classify_content, NO_OPINION, NEEDS_REVIEW,
)
from helpers import FakeBackend, E, TEXT


# ── Fake trees ───────────────────────────────────────────────────────
# Main tree with candidates under Images
TREE = NS(children={"Images": NS(children={
    "d": NS(name="deserts", prompts=["desert"]),
    "m": NS(name="memes",   prompts=["meme"]),
    "s": NS(name="shots",   prompts=["shot"]),
})})

# Tree with no subcategories under Images
EMPTY_TREE = NS(children={"Images": NS(children={})})

# Tree with both Images AND Documents children (for gate 1 test)
TREE_WITH_DOCS = NS(children={
    "Images": NS(children={
        "d": NS(name="deserts", prompts=["desert"]),
        "m": NS(name="memes",   prompts=["meme"]),
        "s": NS(name="shots",   prompts=["shot"]),
    }),
    "Documents": NS(children={
        "r": NS(name="reports", prompts=["report"]),
    }),
})


# ── Broken backend for containment test ──────────────────────────────
class BrokenBackend(FakeBackend):
    def encode_texts(self, texts):
        raise RuntimeError("boom")


# ── Gate tests ───────────────────────────────────────────────────────
def test_confident_match(monkeypatch, sample_image):
    """Image vector E[1] aligns with 'meme' → subfolder 'memes', confidence ~1.0."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1]))
    d = classify_content(sample_image, "Images", TREE)
    assert d.subfolder == "memes"
    assert d.confidence == pytest.approx(1.0)
    assert d.embedding is not None


def test_below_threshold(monkeypatch, sample_image):
    """Image vector E[3] orthogonal to all → NEEDS_REVIEW, confidence 0.0 (not None)."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[3]))
    d = classify_content(sample_image, "Images", TREE)
    assert d.subfolder == NEEDS_REVIEW
    assert d.confidence == pytest.approx(0.0)
    assert d.confidence is not None   # judged but unsure, NOT "never looked"


def test_wrong_category(monkeypatch, sample_image):
    """top_category='Documents' → Gate 1 rejects → NO_OPINION.

    The tree has Documents children with prompts, and docs_text maps "report"
    to E[1] (matching the image vector). Without gate 1, CLIP would return a
    confident result instead of crashing with KeyError.
    """
    docs_text = {**TEXT, "report": E[1]}
    monkeypatch.setattr(image, "backend", FakeBackend(docs_text, E[1]))
    d = classify_content(sample_image, "Documents", TREE_WITH_DOCS)
    assert d == NO_OPINION


def test_unsupported_extension(monkeypatch, tmp_path):
    """A .gif image under Images → Gate 2 rejects → NO_OPINION.

    We save a real image as .gif so PIL CAN open it. Without gate 2,
    CLIP would happily classify it and return a real result.
    """
    p = tmp_path / "funny.gif"
    Image.new("RGB", (8, 8)).save(p)
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1]))
    d = classify_content(p, "Images", TREE)
    assert d == NO_OPINION


def test_no_candidates(monkeypatch, sample_image):
    """Tree has no subcategories under Images → Gate 3 rejects → NO_OPINION.

    Assert the model was never asked to encode anything — without gate 3,
    encode_texts([]) would crash, but that's the wrong reason to pass.
    """
    fake = FakeBackend(TEXT, E[1])
    monkeypatch.setattr(image, "backend", fake)
    d = classify_content(sample_image, "Images", EMPTY_TREE)
    assert d == NO_OPINION
    assert fake.text_calls == 0   # model was never consulted


def test_model_unavailable(monkeypatch, sample_image):
    """Backend refuses to load → Gate 4 rejects → NO_OPINION."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1], loaded=False))
    d = classify_content(sample_image, "Images", TREE)
    assert d == NO_OPINION


def test_missing_file(monkeypatch, tmp_path):
    """File doesn't exist → classify_image returns None → Gate 4 → NO_OPINION."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1]))
    d = classify_content(tmp_path / "ghost.jpg", "Images", TREE)
    assert d == NO_OPINION


def test_containment(monkeypatch, sample_image):
    """encode_texts raises → try/except catches it → NO_OPINION, no exception escapes."""
    monkeypatch.setattr(image, "backend", BrokenBackend(TEXT, E[1]))
    d = classify_content(sample_image, "Images", TREE)
    assert d == NO_OPINION


# ── Threshold passthrough ────────────────────────────────────────────
def test_threshold_reaches_pick_folder(monkeypatch, sample_image):
    """Perfect match + high threshold → NEEDS_REVIEW, proving threshold is forwarded."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1]))
    d = classify_content(sample_image, "Images", TREE, threshold=1.5)
    assert d.subfolder == NEEDS_REVIEW
    assert d.confidence == pytest.approx(1.0)


# ── Real tree test ───────────────────────────────────────────────────
class AnyTextBackend(FakeBackend):
    """A fake that returns a consistent unit vector for any prompt string."""
    def encode_texts(self, texts):
        self.text_calls += 1
        import numpy as np
        # Return a unit vector along dim 0 for every prompt
        return np.tile(E[0], (len(texts), 1))


def test_real_tree_has_candidates(monkeypatch, sample_image):
    """Load the actual category YAML and verify classify_content finds candidates.

    Catches key-casing mismatches between the fake tree and the real one.
    """
    from sortie.core.config import CategoryNode
    real_tree = CategoryNode.load_category_tree()

    monkeypatch.setattr(image, "backend", AnyTextBackend({}, E[0]))
    d = classify_content(sample_image, "Images", real_tree)
    # Should NOT be NO_OPINION — the real tree has Image subcategories
    assert d != NO_OPINION
    assert d.subfolder is not None
    assert d.confidence is not None
