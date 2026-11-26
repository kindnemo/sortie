"""Shared test helpers — FakeBackend, vectors, and constants."""

import numpy as np


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
        self.text_calls += 1
        return np.stack([self.text_vecs[t] for t in texts])

    def encode_image(self, img):
        return self.image_vec


# 4 orthogonal unit vectors — enough to test all the math
E = np.eye(4, dtype=np.float32)
CANDS = [("deserts", ["desert"]), ("memes", ["meme"]), ("shots", ["shot"])]
TEXT = {"desert": E[0], "meme": E[1], "shot": E[2]}
