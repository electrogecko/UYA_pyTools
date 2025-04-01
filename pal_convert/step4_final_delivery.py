import os
import shutil
# Move pal (renamed) and ntsc map files into one singular folder. 

# Set the base folder and dry_run flag
base_folder = r'H:\ps2\fix_pal'
dry_run = True  # Set to False to perform actions instead of just printing

# Create the destination folder "total_out" if it doesn't exist
dest_folder = os.path.join(base_folder, "total_out")
if not os.path.exists(dest_folder):
    print(f"Would create folder: {dest_folder}")
    if not dry_run:
        os.makedirs(dest_folder)
else:
    print(f"Folder already exists: {dest_folder}")

# Define the pal_outputs folder inside the uya folder
pal_outputs_folder = os.path.join(base_folder, "pal_outputs")

# Process files in pal_outputs folder
if os.path.exists(pal_outputs_folder):
    for file_name in os.listdir(pal_outputs_folder):
        source_file = os.path.join(pal_outputs_folder, file_name)
        if os.path.isfile(source_file):
            if file_name.endswith(".version"):
                dest_file = os.path.join(dest_folder, file_name)
                print(f"Would copy {source_file} to {dest_file}")
                if not dry_run:
                    shutil.copy2(source_file, dest_file)
            else:
                # Insert '.pal' before the extension
                base_name, ext = os.path.splitext(file_name)
                new_name = f"{base_name}.pal{ext}"
                dest_file = os.path.join(dest_folder, new_name)
                print(f"Would rename {source_file} to {dest_file}")
                if not dry_run:
                    shutil.copy2(source_file, dest_file)
else:
    print(f"Folder not found: {pal_outputs_folder}")

# Define the products folder inside the uya folder
products_folder = os.path.join(base_folder, "uya")

# Process files in products folder (copy as-is)
if os.path.exists(products_folder):
    for file_name in os.listdir(products_folder):
        source_file = os.path.join(products_folder, file_name)
        if os.path.isfile(source_file):
            dest_file = os.path.join(dest_folder, file_name)
            print(f"Would copy {source_file} to {dest_file}")
            if not dry_run:
                shutil.copy2(source_file, dest_file)
else:
    print(f"Folder not found: {products_folder}")
