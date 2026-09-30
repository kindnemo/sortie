from collections import defaultdict
import yaml
import shutil
from pathlib import Path

class CategoryNode:
    """
    Represents a category node from the YAML structure into a tree-like format. Each node has a name, a list of prompts, and optional child nodes.

    Will read the YAML from category_config.yaml and convert it into a tree structure of CategoryNode objects. Each node can have multiple children that will enable the CategoryNode to be represented into a hierarchical structure.
    """

    def __init__(self, name, prompts=None, children=None):
        self.name = name 
        self.prompts = prompts or []
        self.children = children or {}

    def to_dict(self):
        """
        Converts the CategoryNode and its children into a dictionary format suitable for YAML serialization.

        Args:
            None
        Returns:
            dict: A dictionary representation of the CategoryNode and its children.
        """
        # if self.children:
        #     return {name: child.to_dict() for name, child in self.children.items()} 

        category_dict = {

        }

        # For container nodes with no prompts
        if not self.prompts and self.children:
            pass
        elif len(self.prompts) == 1:
        # For simple nodes with only one prompt and no ensemble
            category_dict["primary"] = self.prompts[0]
        elif len(self.prompts) > 1:
            # For deep nodes with many children and ensemble
            category_dict["primary"] = self.prompts[0]
            category_dict["ensemble"] = self.prompts
        
        # adding children to category dict if they exist
        if self.children:
            category_dict["children"] = {
                name: child.to_dict() for name, child in self.children.items()
                # Using recursion to call the function in on itself to fill the children leaf
            } 
        return category_dict


    @staticmethod
    def from_dict(name, data):
        """
        Creates a CategoryNode from a dictionary representation.

        Args:
            data (dict): A dictionary representation of a CategoryNode.

        Returns:
            CategoryNode: A CategoryNode object created from the dictionary.    
        """

        if "ensemble" in data:
            prompts = data["ensemble"]
        elif "primary" in data:
            prompts = [data["primary"]]
        else:
            prompts = []

        children = {}

        if "children" in data:
            for child_name, child_data in data["children"].items():
                children[child_name] = CategoryNode.from_dict(child_name, child_data)

        return CategoryNode(name, prompts, children)