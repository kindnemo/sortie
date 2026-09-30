import platformdirs 
from pathlib import Path


def data_dir():
    """
    Return the path to the data directory for the application and create it if it doesn't exist.

    Args: 
        None
    Returns: 
        Path: absolute path to the application's data directory.
    """

    storing_path =  Path(platformdirs.user_data_dir("sortie", "sortie"))
    storing_path.mkdir(parents=True, exist_ok=True)
    return storing_path


def data_path(filename):
    """
    Return the path to a specific data file in the data directory.

    Args:
        filename (str): name of the file to locate inside the data directory.
    Returns:
        Path: full path to that file, joined onto the data directory.
        The file itself is not created here.

    """

    return data_dir() / filename


def model_cache_dir():
    """
    Return the path to the model cache directory and create it if it doesn't exist.
    
    Args:
        None
    Returns: 
        Path: absolute path to the "models" subdirectory inside the data directory.
    """

    models_path = data_dir() / "models"
    models_path.mkdir(parents=True, exist_ok=True)
    return models_path