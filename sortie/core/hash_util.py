import hashlib

def compute_file_hash(file_path, chunk_size = 1024*1024):
    """
    Computes an SHA-256 hash of a file content
    
    Args:
        file_path (str): path to the file to hash
        chunk_size (int): size of chunks to read at a time (default: 1MB)
    Returns:
        str: the hexadecimal representation of the SHA-256 hash
    """

    hasher = hashlib.sha256()

    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()