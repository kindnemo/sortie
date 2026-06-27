import time
from pathlib import Path


# def wait_for_file_completion(file_path: str, poll_interval: int =2, timeout: int = 300) -> bool:
#     """ 
#     Waits for a file to finish being written to disk before proceeding. This is useful in scenarios where files are being copied or downloaded and we have to ensure that it is fully written and unlocked by the OS before we can process it. This function checks the file size at regular intervals for growth and if it remains constant for a certain number of checks, it assumes the file is done being written

#     Args: 
#         file_path (str): The absolute path to the file.
#         poll_interval (int): Seconds to wait between checks. Defaults to 2 seconds.
#         timeout (int): Maximum time to wait before giving up. Defaults to 5 minutes.
#     Returns:
#         bool: True if the file is done being written, False otherwise.
#     """

#     path = Path(file_path)
#     start_time = time.time()
#     previous_size = -1

#     while (time.time() - start_time) < timeout:
#         # Checking if the file exists at all  
#         if not path.exists():
#             print(f"[JIT] File {file_path} does not exist. Waiting...")
#             return 

#         try: 
#             # Gets the current file size
#             current_size = path.stat().st_size 

#             if (current_size == previous_size) and (current_size > 0):
#                 os.rename(file_path, file_path)  # Attempting to rename the file to check if it's locked
#                 print(f"file {file_path} is completed and unlocked {path.name}")
#                 return True
#             previous_size = current_size
        
#         except PermissionError:
#             # If the file is locked we move onto the next interval
#             pass
#         except OSError as e:
#             # Catching other random OS-level errors
#             pass

#         # Waiting before checking again
#         time.sleep(poll_interval)
    
#     print(f"Timed out waiting for file {file_path} to complete.")
#     return False


def wait_for_file_completion(file_path: str, poll_interval: int = 0.25, timeout: int = 300) -> bool:

    """ 
     Waits for a file to finish being written to disk before proceeding. This is useful in scenarios where files are being copied or downloaded and we have to ensure that it is fully written and unlocked by the OS before we can process it. This function checks the file size at regular intervals for growth and if it remains constant for a certain number of checks, it assumes the file is done being written

     Args: 
         file_path (str): The absolute path to the file.
         poll_interval (int): Seconds to wait between checks. Defaults to 2 seconds.
         timeout (int): Maximum time to wait before giving up. Defaults to 5
         minutes.
     Returns:
         bool: True if the file is done being written, False otherwise.
    """


    path = Path(file_path)
    start_time = time.time()
    previous_size = -1
    stable_count = 0
    last_missing_log = 0

    while (time.time() - start_time) < timeout:
        try:
            #checking if files exists and its size
            current_size = path.stat().st_size

            if current_size == previous_size:
                stable_count += 1
            else:
                stable_count = 0
            
            previous_size = current_size

            # Checking stable count
            if stable_count >= 2:
                # Checking if the path is unlocked by trying to modify the file, idk gemini suggested it to me I'm still skeptical about this
                with open(path, 'a'):
                    pass
                
                print (f"File {path.name} is complete and unlocked")
                return True
        
        except FileNotFoundError:
            if time.time() - last_missing_log >= poll_interval:
                print(f"file {path.name} not found. Retrying...")
                last_missing_log = time.time()
        except PermissionError:
            print(f"File {path.name} is locked. Retrying...")
        except OSError as e:
            print(f"OS Error: {e}")
            # Resetting the stable count to 0 after an OS error
            stable_count = 0

        time.sleep(poll_interval)
    
    print(f"Timed out waiting for file {path.name} to complete.")
    return False

