_model = None
_preprocess = None
_tokenizer = None
_load_failed = False

MODEL_NAME = "ViT-B-16"
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
