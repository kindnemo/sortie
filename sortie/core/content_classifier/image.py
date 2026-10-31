from sortie.core.config import CategoryNode

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
        (child.name, child.prompts)
    ]