import sqlite3
import json
import numpy as np
from sortie.paths import data_path
from datetime import datetime
from sortie.core.hash_util import compute_file_hash

def _connect():
    """
    Open a connection to the movelog database, creating the database
    file and its tables if they don't exist yet.

    Args:
        None
    Returns:
        sqlite3.Connection: open connection to movelog.db
    """

    conn = sqlite3.connect(str(data_path("movelog.db")))
    conn.row_factory = sqlite3.Row

    conn.execute("""CREATE TABLE IF NOT EXISTS moves (
                    id integer PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    source_path TEXT,
                    dest_path TEXT,
                    chain TEXT,
                    confidence REAL,
                    needs_review INTEGER,
                    undone INTEGER DEFAULT 0
                )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS embeddings(
                    id integer PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE,
                    file_hash TEXT,
                    model_name TEXT,
                    modality TEXT,
                    embedding BLOB,
                    created_at TEXT
                )""")


    # Create an index on the embeddings table for faster lookups by file_hash
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_embeddings_hash ON embeddings(file_hash)""")
    
    return conn


def log_move(source_path, dest_path, chain, confidence, needs_review):
    """
    Insert one row into the moves table recording a file move.

    Args:
        source_path (str): where the file was moved from
        dest_path (str): where the file was moved to
        chain (list): the category chain, e.g. ["Documents", "Work"]
        confidence (float or None): classifier confidence for this move
        needs_review (bool): whether this move needs manual review
    Returns:
        None
    """

    chain_json = json.dumps(chain)

    needs_review_int = 1 if needs_review else 0

    timestamp = datetime.now().isoformat()

    conn = _connect()

    conn.execute("""INSERT INTO moves (
                timestamp, source_path, dest_path, chain, confidence, needs_review) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (timestamp, source_path, dest_path, chain_json, confidence, needs_review_int))

    conn.commit()
    conn.close()



def get_recent_moves(limit = 25):
    """
    Return the most recent moves, newest first.

    Args:
        limit (int): maximum number of rows to return
    Returns:
        list[dict]: each dict has the moves table's columns, with
                     chain as a list and needs_review/undone as bool
    """

    conn = _connect()
    rows = conn.execute("SELECT * FROM moves ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()

    moves = []

    for row in rows:
        move = {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "source_path": row["source_path"],
            "dest_path": row["dest_path"],
            "chain": json.loads(row["chain"]),
            "confidence": row["confidence"],
            "needs_review": bool(row["needs_review"]),
            "undone": bool(row["undone"]),
        }

        moves.append(move)

    return moves



def get_move(move_id):
    """
    Return a single move by id.

    Args:
        move_id (int): the id of the move to look up
    Returns:
        dict or None: the move's data (same shape as get_recent_moves's
                       dicts), or None if no row matches move_id
    """

    conn = _connect()

    row = conn.execute("SELECT * FROM moves WHERE id = ?", (move_id,)).fetchone()

    conn.close()

    if row is None:
        return None

    move = {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "source_path": row["source_path"],
            "dest_path": row["dest_path"],
            "chain": json.loads(row["chain"]),
            "confidence": row["confidence"],
            "needs_review":bool(row["needs_review"]),
            "undone": bool(row["undone"]),
            }
    return move


def mark_undone(move_id):
    """
    Mark a move as undone.

    Args:
        move_id (int): the id of the move to mark undone
    Returns:
        None
    """

    conn = _connect()

    conn.execute("UPDATE moves SET undone = 1 where id = ?", (move_id,))

    conn.commit()
    conn.close()



def store_embedding(file_path, embedding, model_name, modality, file_hash = None):
    """
    Store (or update) the embedding for a file.

    Args:
        file_path (str): path of the file this embedding belongs to
        embedding (np.ndarray): the embedding vector
        model_name (str): name of the model used to generate the embedding
        modality (str): e.g. "image" or "text"
        file_hash (str or None): the SHA-256 hash of the file; if None
    Returns:
        None
    """

    embedding_bits = embedding.astype(np.float32).tobytes()
    created_at = datetime.now().isoformat()
    if file_hash is None:
        file_hash = compute_file_hash(file_path)

    conn = _connect()

    conn.execute("""INSERT OR REPLACE INTO embeddings (file_path, file_hash, model_name, modality, embedding, created_at)
                 VALUES (?, ?, ?, ?, ?, ?)""", 
                 (file_path, file_hash, model_name, modality, embedding_bits, created_at))

    conn.commit()
    conn.close()


def get_all_embeddings(model_name, modality = None):
    """
    Return stored embeddings, filtered by model and (optionally) modality.

    Args:
        model_name (str): the model whose embeddings to fetch
        modality (str or None): if given, further filter to this modality
                                 (e.g. "image" or "text"); if None, return
                                 all modalities for this model
    Returns:
        list[dict]: each dict has file_path, file_hash, model_name,
                     modality, embedding (np.ndarray), and created_at
    """

    conn = _connect()
    if modality is None:
        query = "SELECT * FROM embeddings WHERE model_name = ?"
        params = (model_name,)
    else:
        query = "SELECT * from embeddings WHERE model_name = ? AND modality = ?"
        params = (model_name, modality,)

    rows = conn.execute(query, params).fetchall()

    conn.close()
    embeds = []
    for row in rows:
        entry = {
            "id": row["id"], 
            "file_path": row["file_path"],
            "file_hash": row["file_hash"],
            "model_name": row["model_name"],
            "modality": row["modality"],
            "embedding": np.frombuffer(row["embedding"], dtype=np.float32),
            "created_at": row["created_at"]
        }

        embeds.append(entry)
    return embeds


def delete_embedding(file_path):
    conn = _connect()
    conn.execute("DELETE FROM embeddings WHERE file_path = ?", (file_path, ))
    conn.commit()
    conn.close()


def get_embedding_by_hash(file_hash, model_name, modality):
    """
    Return the embedding for a file using its hash
    
    Args:
        file_hash (str): the SHA-256 hash of the file
        model_name (str): the name of the model
        modality (str): the modality of the embedding
    Returns:
        np.ndarray or None: the embedding vector, or None if not found
    """

    conn = _connect()
    row = conn.execute("SELECT * FROM embeddings WHERE file_hash = ? AND model_name = ? AND modality = ?", (file_hash, model_name, modality)).fetchone()   #Fetchone is used only for cache check use case for now, change this if trying to use for duplicate detection 
    conn.close()

    if row is None:
        return None

    return np.frombuffer(row["embedding"], dtype=np.float32)