import json

import numpy as np
import pytest

from sortie.core import movelog


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    # Redirect movelog's data_path so _connect() opens a throwaway
    # database in tmp_path instead of your real AppData folder.
    db_file = tmp_path / "movelog.db"
    monkeypatch.setattr(movelog, "data_path", lambda filename: db_file)
    return db_file


# ---------- log_move / get_recent_moves ----------

def test_log_move_and_get_recent_moves(fresh_db):
    movelog.log_move(
        "/tmp/test.jpg", "/sorted/Images/test.jpg",
        ["Images"], 0.9, False,
    )
    moves = movelog.get_recent_moves()
    assert len(moves) == 1
    assert moves[0]["dest_path"] == "/sorted/Images/test.jpg"


def test_log_move_chain_round_trips_as_list(fresh_db):
    movelog.log_move(
        "/tmp/a.pdf", "/sorted/Docs/a.pdf",
        ["Documents", "Work"], 0.8, False,
    )
    moves = movelog.get_recent_moves()
    assert moves[0]["chain"] == ["Documents", "Work"]
    assert isinstance(moves[0]["chain"], list)


def test_log_move_needs_review_is_bool(fresh_db):
    movelog.log_move("/a", "/b", ["X"], 0.5, True)
    moves = movelog.get_recent_moves()
    assert moves[0]["needs_review"] is True
    assert isinstance(moves[0]["needs_review"], bool)


def test_log_move_confidence_can_be_none(fresh_db):
    movelog.log_move("/a", "/b", ["X"], None, False)
    moves = movelog.get_recent_moves()
    assert moves[0]["confidence"] is None


def test_get_recent_moves_order_is_newest_first(fresh_db):
    movelog.log_move("/1", "/d1", ["X"], 0.1, False)
    movelog.log_move("/2", "/d2", ["X"], 0.2, False)
    movelog.log_move("/3", "/d3", ["X"], 0.3, False)
    moves = movelog.get_recent_moves()
    assert [m["source_path"] for m in moves] == ["/3", "/2", "/1"]


def test_get_recent_moves_respects_limit(fresh_db):
    for i in range(5):
        movelog.log_move(f"/{i}", f"/d{i}", ["X"], 0.1, False)
    moves = movelog.get_recent_moves(limit=2)
    assert len(moves) == 2


# ---------- get_move ----------

def test_get_move_returns_matching_row(fresh_db):
    movelog.log_move("/src", "/dest", ["X"], 0.7, False)
    inserted_id = movelog.get_recent_moves()[0]["id"]
    row = movelog.get_move(inserted_id)
    assert row is not None
    assert row["source_path"] == "/src"


def test_get_move_returns_none_when_missing(fresh_db):
    assert movelog.get_move(9999) is None


# ---------- mark_undone ----------

def test_mark_undone_sets_flag(fresh_db):
    movelog.log_move("/src", "/dest", ["X"], 0.7, False)
    move_id = movelog.get_recent_moves()[0]["id"]

    movelog.mark_undone(move_id)

    row = movelog.get_move(move_id)
    assert row["undone"] is True


def test_moves_start_as_not_undone(fresh_db):
    movelog.log_move("/src", "/dest", ["X"], 0.7, False)
    row = movelog.get_recent_moves()[0]
    assert row["undone"] is False


# ---------- store_embedding / get_all_embeddings ----------

def make_vector(seed=0):
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


def test_store_and_retrieve_embedding(fresh_db):
    vec = make_vector()
    movelog.store_embedding("/tmp/a.jpg", vec, "ViT-B-16", "image")

    rows = movelog.get_all_embeddings("ViT-B-16", "image")
    assert len(rows) == 1
    assert rows[0]["file_path"] == "/tmp/a.jpg"
    assert rows[0]["embedding"].shape == (512,)
    assert rows[0]["embedding"].dtype == np.float32
    np.testing.assert_allclose(rows[0]["embedding"], vec, rtol=1e-5)


def test_store_embedding_replaces_not_duplicates(fresh_db):
    vec1 = make_vector(seed=1)
    vec2 = make_vector(seed=2)

    movelog.store_embedding("/tmp/a.jpg", vec1, "ViT-B-16", "image")
    movelog.store_embedding("/tmp/a.jpg", vec2, "ViT-B-16", "image")

    rows = movelog.get_all_embeddings("ViT-B-16", "image")
    assert len(rows) == 1
    np.testing.assert_allclose(rows[0]["embedding"], vec2, rtol=1e-5)


def test_get_all_embeddings_filters_by_model(fresh_db):
    movelog.store_embedding("/a.jpg", make_vector(1), "ViT-B-16", "image")
    movelog.store_embedding("/b.jpg", make_vector(2), "other-model", "image")

    rows = movelog.get_all_embeddings("ViT-B-16")
    assert len(rows) == 1
    assert rows[0]["file_path"] == "/a.jpg"


def test_get_all_embeddings_filters_by_modality(fresh_db):
    movelog.store_embedding("/a.jpg", make_vector(1), "ViT-B-16", "image")
    movelog.store_embedding("/a.txt", make_vector(2), "ViT-B-16", "text")

    rows = movelog.get_all_embeddings("ViT-B-16", modality="text")
    assert len(rows) == 1
    assert rows[0]["file_path"] == "/a.txt"


# ---------- delete_embedding ----------

def test_delete_embedding_removes_row(fresh_db):
    movelog.store_embedding("/a.jpg", make_vector(), "ViT-B-16", "image")
    movelog.delete_embedding("/a.jpg")

    rows = movelog.get_all_embeddings("ViT-B-16")
    assert rows == []