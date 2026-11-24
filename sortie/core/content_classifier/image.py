import numpy as np
from sortie.core.content_classifier.clip_model import backend
from typing import NamedTuple
import logging
logger = logging.getLogger(__name__)

class ImageResult(NamedTuple):
    # Represents the result of classifying an image.
    name: str
    confidence: float
    embedding: np.ndarray


THRESHOLD = 0.22  # Placeholder. Calibrating later
_text_cache = {}


def image_candidates(tree):
    """
    Returns [(subcategory_name, [prompt])] for all prompts in the branch.

    Args:
        tree (CategoryNode): The root of the category tree.
    """

    images = tree["images"] 
    return[
        (c.name, c.prompts) for c in images.children.values() if c.prompts
    ]


def _text_features(candidates):
    """
    Converts each subcategory's text prompts into a single noramlized CLIP embedding vector along with caching

    Args:
        candidates (list): List of tuples containing subcategory names and their corresponding prompts.
    Returns:
         (K, 512) array
    """

    key = tuple((name, tuple(prompts)) for name, prompts in candidates)
    if key in _text_cache:
        return _text_cache[key]

    flat = [p for _, prompts in candidates for p in prompts]
    f = backend.encode_texts(flat)
    rows, i = [], 0

    for _, prompts in candidates:
        avg = f[i:i+len(prompts)].mean(axis=0)
        rows.append(avg/np.linalg.norm(avg))
        i += len(prompts)

    out = np.stack(rows)
    _text_cache[key] = out
    return out


def image_features(path):
    """ Converts an image into a normalized CLIP embedding vector. """
    

    from PIL import Image
    with Image.open(path) as img:
        return backend.encode_image(img)

def score_image(path, candidates):
    """
    Computes the cosine similarity between the image and every candidates subcategory's

    Args:
        path (str): Path to the image file.
        candidates (list): List of tuples containing subcategory names and their corresponding prompts.
    Returns:
        (scores, embedding)
    """
    # Making sure that the model is loaded into memory, return None if not
    if not backend.ensure_loaded():
        return None, None

    try:
        img_f = image_features(path)
    except Exception as e:
        print(f"Error processing image {path}: {e}")
        logger.warning("Error Processing image %s: %s", path, e)
        return None, None

    sims = img_f @ _text_features(candidates).T
    return sims.tolist(), img_f

def classify_image(path, candidates):
    """
    Returns the highest scoring subcategory for the image, if it exceeds the threshold.

    Args:
        path (str): Path to the image file.
        candidates (list): List of tuples containing subcategory names and their corresponding prompts.
    Returns:
        ImageResult or None: A named tuple containing name of the candidate, confidence level and embedding
    """
    scores, img_f = score_image(path, candidates)
    if scores is None:
        return None
    best = max(range(len(scores)), key = scores.__getitem__)
    return ImageResult(name = candidates[best][0], confidence = float(scores[best]), embedding = img_f)

def pick_folder(name, confidence, threshold = THRESHOLD):
    # Picks the folder if the confidence is above the threshold, otherwise returns None
    return name if confidence >= threshold else None