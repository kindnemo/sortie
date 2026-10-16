from sortie.core.hash_util import compute_file_hash


def test_compute_file_hash_returns_known_sha256(tmp_path):
    file_path = tmp_path / "known.txt"
    file_path.write_bytes(b"hello world")

    assert compute_file_hash(file_path) == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_compute_file_hash_returns_empty_input_sha256(tmp_path):
    file_path = tmp_path / "empty.txt"
    file_path.write_bytes(b"")

    assert compute_file_hash(file_path) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_compute_file_hash_is_content_based(tmp_path):
    first_path = tmp_path / "first.txt"
    same_content_path = tmp_path / "same.txt"
    different_content_path = tmp_path / "different.txt"
    first_path.write_bytes(b"same content")
    same_content_path.write_bytes(b"same content")
    different_content_path.write_bytes(b"different content")

    first_hash = compute_file_hash(first_path)
    assert compute_file_hash(same_content_path) == first_hash
    assert compute_file_hash(different_content_path) != first_hash
