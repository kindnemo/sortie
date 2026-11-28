import logging
from pathlib import Path
from typing import NamedTuple
import numpy as np
from sortie.core.content_classifier.image import (
    image_candidates, classify_image, pick_folder, THRESHOLD
)
logger = logging.getLogger(__name__)

class ContentDecision(NamedTuple):
    subfolder: str | None  # None = "no opinion"
    confidence: float | None = None # None = never judged; a number = the model judged
    embedding: np.ndarray | None = None

NO_OPINION = ContentDecision(None)
NEEDS_REVIEW = "Needs Review"
IMAGE_EXTENSION = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

def classify_content(path, top_category, tree, threshold=THRESHOLD):
    """
    Bridge between watcher and CLIP to know if CLIP has classified the file or not
    """

    try:
        # Gate 1: checking if it is an Image
        if top_category.lower() != "images":  return NO_OPINION

        # Gate 2: checking if the extension is supported since CLIP can't handle all image file types like svg, .gif, .raw
        if Path(path).suffix.lower() not in IMAGE_EXTENSION : return NO_OPINION

        # Gate 3: Checking if TreeNode has image_candidates
        cands = image_candidates(tree)
        if not cands: return NO_OPINION

        # Gate 4: checking if CLIP has classified or not
        result = classify_image(path, cands)
        if result is None:
            return NO_OPINION

        # Gate 5: Checking if confidence is higher than threshold
        folder = pick_folder(result.name, result.confidence, threshold)
        if folder is None:
            return ContentDecision(NEEDS_REVIEW, result.confidence, result.embedding)

        return ContentDecision(folder, result.confidence, result.embedding)


    except Exception:
        logger.exception("content classification failed for %s", path)
        return NO_OPINION