import numpy as np
import pytest
from PIL import Image
from sortie.core.content_classifier import image


# ── FakeBackend ──────────────────────────────────────────────────────
class FakeBackend:
    def __init__(self, text_vecs, image_vec, loaded=True):
        self.text_vecs = text_vecs      # {"prompt string": np.array}
        self.image_vec = image_vec
        self.loaded = loaded
        self.text_calls = 0

    def ensure_loaded(self):
        return self.loaded

    def is_loaded(self):
        return self.loaded

    def encode_texts(self, texts):
        self.text_calls+=1
        return np.stack([self.text_vecs[t] for t in texts])

    def encode_image(self, img):
        return self.image_vec


# ── Fixtures ─────────────────────────────────────────────────────────
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


# ── Shared test vectors ──────────────────────────────────────────────
E = np.eye(4, dtype=np.float32)   # 4 orthogonal unit vectors
CANDS = [("deserts", ["desert"]), ("memes", ["meme"]), ("shots", ["shot"])]
TEXT = {"desert": E[0], "meme": E[1], "shot": E[2]}


# ── pick_folder (pure function, no fakes needed) ─────────────────────
def test_pick_folder_above_threshold():
    assert image.pick_folder("memes", 0.5, threshold=0.4) == "memes"


def test_pick_folder_below_threshold():
    assert image.pick_folder("memes", 0.3, threshold=0.4) is None


def test_pick_folder_at_threshold():
    assert image.pick_folder("memes", 0.4, threshold=0.4) == "memes"


# ── classify_image with FakeBackend ──────────────────────────────────
def test_picks_aligned_candidate(monkeypatch, sample_image):
    """Image vector E[1] aligns perfectly with 'meme' → expect 'memes', confidence ~1.0."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1]))
    r = image.classify_image(sample_image, CANDS)
    assert r is not None
    assert r.name == "memes"
    assert r.confidence == pytest.approx(1.0)
    assert isinstance(r.confidence, float)      # not np.float32 → safe for SQLite


def test_unrelated_vector(monkeypatch, sample_image):
    """Image vector E[3] is orthogonal to all candidates → all scores 0."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[3]))
    r = image.classify_image(sample_image, CANDS)
    assert r is not None                         # still returns a result, just low confidence
    assert r.confidence == pytest.approx(0.0)
    assert image.pick_folder(r.name, r.confidence) is None   # below any sane threshold


def test_unloaded_backend(monkeypatch, sample_image):
    """Backend refuses to load → classify_image returns None, no crash."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1], loaded=False))
    r = image.classify_image(sample_image, CANDS)
    assert r is None


# ── Optional extras ──────────────────────────────────────────────────
def test_missing_file(monkeypatch, tmp_path):
    """Path doesn't exist, loaded fake → expect None (image_features fails)."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[1]))
    r = image.classify_image(tmp_path / "no_such_file.jpg", CANDS)
    assert r is None


def test_cache_hit(monkeypatch, sample_image):
    """Two calls with the same candidates should produce only one cache entry."""
    fake = FakeBackend(TEXT, E[0])
    monkeypatch.setattr(image, "backend", fake)
    image.classify_image(sample_image, CANDS)
    image.classify_image(sample_image, CANDS)
    assert fake.text_calls == 1


def test_threshold_passthrough(monkeypatch, sample_image):
    """Same result lands in different folders depending on the threshold."""
    monkeypatch.setattr(image, "backend", FakeBackend(TEXT, E[0]))
    r = image.classify_image(sample_image, CANDS)
    # confidence is ~1.0, so a low threshold accepts and a high one rejects
    assert image.pick_folder(r.name, r.confidence, threshold=0.5) == "deserts"
    assert image.pick_folder(r.name, r.confidence, threshold=1.5) is None

def test_averaging_renormalizes(monkeypatch, sample_image):
    cands = [("shots", ["a", "b"])]
    text = {"a": E[0], "b": E[1]}
    monkeypatch.setattr(image, "backend", FakeBackend(text, E[0]))
    r = image.classify_image(sample_image, cands)
    assert r.confidence == pytest.approx(0.707, abs=1e-3)
