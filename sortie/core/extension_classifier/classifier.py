import argparse
import sys
import time 
import shutil
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sortie.core.extension_classifier.JIT import wait_for_file_completion
from sortie.core.extension_classifier.extension_map import EXT_MAP


# Defining a category folder for cross-validating the sub-folders in Handler functions
category_folders = set(EXT_MAP.values()) | {"Others"}

# Directory to monitor
WATCH_DIRECTORY = Path("D:/sortie-test-folder")

# Classifying files based on their extensions and moving them to respective folders 
class FileClassifier: 
    def __init__(self, watch_directory: Path = WATCH_DIRECTORY):
        self.watch_directory = Path(watch_directory)

    def classify_file(self, file_path: Path):
        # Defining target folder
        folder_name = EXT_MAP.get(file_path.suffix.lower(), "Others")
        destination_folder = self.watch_directory / folder_name

        # Creating the directory if it doesn't exist
        destination_folder.mkdir(parents=True, exist_ok=True)
        destination_file = destination_folder / file_path.name

        # Preventing moving a file into itself if its already in the right spot 
        if file_path == destination_file:
            return 
        

        # Moving the file to the destination folder
        try:
            shutil.move(str(file_path), str(destination_file))
            print(f"Moved {file_path.name} to {destination_file}")
        except Exception as e:
            print(F"Error Moving file {file_path.name}: {e}")





class OnMyWatch:

    def __init__(self, watch_directory : Path = WATCH_DIRECTORY):  #Defaulting to D directory for now
        self.watch_directory = Path(watch_directory )
        self.observer = Observer()

    def run(self):
        event_handler = Handler(self.watch_directory)
        self.observer.schedule(event_handler, self.watch_directory, recursive=False)
        self.observer.start()
        try:
            while True:
                time.sleep(5) 
        except KeyboardInterrupt:
            self.observer.stop()
            print("Observer Stopped")
        
        self.observer.join()


# Handler class to handle all events
class Handler(FileSystemEventHandler):
    def __init__(self, watch_directory: Path):
        self.watch_directory = watch_directory


    # Main File Handler Function
    def handle_files(self, file_path: Path):
        # Checking if a file is already in a subfolder to prevent infinite calling of the JIT function 
        if file_path.parent.name in category_folders:
            return

        extension = file_path.suffix.lower()

        # Ignoring temporary placeholder files form chrome and firefox
        if extension == ".tmp" or extension == ".crdownload":
            return 
        print(f"Hey, {file_path} is ready!")
        print(f"File name: {file_path.name}, Extension: {file_path.suffix}")

        # Skipping the handling if the path doesn't exist
        if not file_path.exists():
            return 
        

        if not wait_for_file_completion(file_path):
            return
        # Classifying the file based on its extension
        classifier = FileClassifier(self.watch_directory)
        classifier.classify_file(file_path)

    def on_created(self, event):
        if event.is_directory:
            return None

        self.handle_files(Path(event.src_path))
    
    
    def on_moved(self, event):
        if event.is_directory:
            return None
        self.handle_files(Path(event.dest_path))


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Watch a folder and sort files by extension.")
    parser.add_argument(
        "watch_directory",
        nargs="?",
        default=str(WATCH_DIRECTORY),
        help=f"Folder to watch. Defaults to {WATCH_DIRECTORY}",
    )
    args = parser.parse_args(argv)

    watch = OnMyWatch(Path(args.watch_directory))
    watch.run()


if __name__ == "__main__":
    main()
