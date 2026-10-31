from sortie.core.config import load_category_tree
from sortie.core.content_classifier.image import image_candidates

tree = load_category_tree()
for name, prompts in image_candidates(tree):
    print(name, len(prompts))