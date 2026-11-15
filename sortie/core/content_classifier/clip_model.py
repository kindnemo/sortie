import logging
import threading
import numpy as np

logger = logging.getLogger(__name__)

_model = None
_preprocess = None
_tokenizer = None
_load_failed = False

MODEL_NAME = "ViT-B-16-quickgelu"  #Changed from ViT-B-32 to ViT-B-16-quickgelu to match the models activation function correctly. This is the model used by OpenAI in their CLIP paper and is the default model used by OpenCLIP.
PRETRAINED = "openai"

def load_clip() -> bool:
    """
    Returns True if the model is ready, False if we should abstain.
    """

    global _model, _preprocess, _tokenizer, _load_failed
    if _model is not None:
        return True
    if _load_failed:
        return False


    try:
        import open_clip
        model, _, _preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)

        model.eval()
        tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    except Exception as e:
        _load_failed = True
        return False

    _model, _preprocess, _tokenizer = model, _preprocess, tokenizer
    return True

class CLIPBackend:

    def is_loaded(self) -> bool:
        return _model is not None

    def ensure_loaded(self) -> bool:
        return load_clip()

    def _require_loaded(self):
        if not self.ensure_loaded():
            raise RuntimeError("CLIP model is not loaded. call ensure_loaded()")

    @staticmethod
    def _normalize(f) -> np.ndarray:
        return (f / f.norm(dim=-1, keepdim=True)).cpu().numpy()
    
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        """
        Returns a normalized embedding for each text in the list.
        """
        self._require_loaded()

        import torch
        tokens = _tokenizer(texts)
        with torch.no_grad():
            f = _model.encode_text(tokens)
        return self._normalize(f)

    def encode_image(self, img) -> np.ndarray:
        self._require_loaded()
        import torch
        tensor = _preprocess(img.convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            f = _model.encode_image(tensor)
        return self._normalize(f)[0]



backend = CLIPBackend()
### Situation	                                                      File lands in	                    Confidence logged
#No image subcategories in the tree, or depth says stop at top level  	Images/	                                NULL
#CLIP failed to load	                                                Images/	                                NULL
#Image can’t be opened (corrupt file)	                                Images/	                                NULL
#Best score is below the threshold	                                    Images/Needs review/	                the score
#Best score is at or above the threshold	                            Images/<Subcategory>/	                the score 