from sortie.core.config import clip_model

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
        dict: A dictionary mapping subcategory names to their normalized CLIP embedding vectors.
    """

    import torch #lazy loading torch to make sure startup time is fast 
    key = tuple((name, tuple(prompts)) for name, prompts in candidates)
    if key in _text_cache:
        return _text_cache[key]

    flat = [p for _, prompts in candidates for p in prompts]
    with torch.no_grad():
        f = clip_model.encode_text(clip_model.tokenizer(flat))
    f = f / f.norm(dim =-1 , keepdim = True)

    rows, i = [], 0

    for _, prompts in candidates:
        avg = f[i : i + len(prompts)].mean(dim = 0)
        rows.append(avg / avg.norm())
        i += len(prompts)

    out = torch.stack(rows)
    _text_cache[key] = out
    return out


def image_features(path):
    """ Converts an image into a normalized CLIP embedding vector. """
    
    import torch
    from PIL import Image
    with Image.open(path) as img:
        tensor = clip_model.preprocess(img.convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        f = clip_model.model.encode_image(tensor)
    return f/f.norm(dim=-1, keepdim=True)

def score_image(path, candidates):
    """
    Computes the cosine similarity between the image and every candidates subcategory's

    Args:
        path (str): Path to the image file.
        candidates (list): List of tuples containing subcategory names and their corresponding prompts.
    Returns:
        list: A list of floats representing the cosine smilarity scores between the image and each subcategory's text prompts.
    """
    # Making sure that the model is loaded into memory, return None if not
    if not clip_model.is_loaded():
        return None, None

    try:
        img_f = image_features(path)
    except Exception as e:
        print(f"Error processing image {path}: {e}")
        return None, None

    sims = (img_f @ _text_features(candidates).T).squeeze(0)
    return sims.tolist(), img_f

def classify_image(path, candidates):
    """
    Returns the highest scoring subcategory for the image, if it exceeds the threshold.

    Args:
        path (str): Path to the image file.
        candidates (list): List of tuples containing subcategory names and their corresponding prompts.
    Returns:
        str or None: The name of the highest scoring subcategory if it exceeds the threshold, otherwise None.
    """
    scores, img_f = score_image(path, candidates)
    if scores is None:
        return None, None
    best = max(range(len(scores)), key = scores.__getitem__)
    return candidates[best][0], scores[best], img_f

def pick_folder(name, confidence, threshold = THRESHOLD):
    # Picks the folder if the confidence is above the threshold, otherwise returns None
    return name if confidence >= threshold else None