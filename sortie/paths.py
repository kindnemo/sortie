import platformdirs 
from pathlib import Path


"""Return the path to the data directory for the application and create it if it doesn't exist."""
def data_dir():
    storing_path =  Path(platformdirs.user_data_dir("sortie", "sortie"))
    storing_path.mkdir(parents=True, exist_ok=True)
    return storing_path


"""Return the path to a specific data file in the data directory."""
def data_path(filename):
    return data_dir() / filename


"""Return the path to the model cache directory and create it if it doesn't exist."""
def model_cache_dir():
    models_path = data_dir() / "models"
    models_path.mkdir(parents=True, exist_ok=True)
    return models_path