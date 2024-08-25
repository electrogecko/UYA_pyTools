# Display an error if shrub model is not multiple of 16 
# Recursive 
import os
import fnmatch

root_folder = "H:\\ps2\\packer\\level46\\assets\\shrub"
filename = "shrub.bin"  # Specify the pattern with wildcards (e.g., '*.txt' for all .txt files)
verbose = True

# Function to recursively go through the files
def check_files(root_folder, filename):
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            # Check if the file matches the pattern
            if fnmatch.fnmatch(file, filename):
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    # Check if the file size is not a multiple of 16
                    if verbose and not file_size % 16 != 0:
                        print(f"File: {file_path}, Size: {file_size} bytes")
                    if file_size % 16 != 0:
                        print(f"File: {file_path}, Size: {file_size} bytes (Not a multiple of 16)")
                except OSError as e:
                    print(f"Error accessing {file_path}: {e}")

# Call the function
check_files(root_folder, filename)
