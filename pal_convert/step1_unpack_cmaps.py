import os
import shutil
import subprocess
import re
# Requires WSL, packer CLI, (and its required MSVCC libraries) 
# Set this flag to False to execute operations.
DRY_RUN = True
# Extract all map files into a 'uya' subfolder (like the usb) 
# Modify unpack.sh to point to Forge tools directory or packer CLI
base_folder = r'H:\ps2\fix_pal'
unpack_script_name = 'unpack.sh'

# Define the UYA folder where all map files reside.
uya_dir = os.path.join(base_folder, 'uya')
if not os.path.isdir(uya_dir):
    raise Exception(f"UYA folder not found: {uya_dir}")

# Gather files and group them by base name.
files = os.listdir(uya_dir)
maps = {}
for file in files:
    base, ext = os.path.splitext(file)
    if ext.lower() in ['.wad', '.world', '.version']:
        maps.setdefault(base, {})[ext.lower()] = file

# Process each map (grouped by base name)
for map_base, file_dict in maps.items():
    # Ensure all three required file types are present.
    if not all(ext in file_dict for ext in ['.wad', '.world', '.version']):
        print(f"Skipping '{map_base}': missing required file types.")
        continue

    # Read the version from the .version file (5th byte, offset 0x04)
    version_path = os.path.join(uya_dir, file_dict['.version'])
    try:
        with open(version_path, 'rb') as vf:
            vf.seek(4)
            version_byte = vf.read(1)
            if not version_byte:
                print(f"Error: Could not read version byte for '{map_base}'.")
                continue
            level_id = version_byte[0]
            print(f"Map '{map_base}': Found version number {level_id}")
    except Exception as e:
        print(f"Error reading version for '{map_base}': {e}")
        continue

    # Validate version range.
    if not (39 <= level_id <= 60):
        print(f"Skipping '{map_base}': level ID {level_id} out of expected range (39-60).")
        continue

    # Create a two-digit string representation of the level ID.
    level_str = f"{level_id:02d}"
    # Instead of using 'levelXX', use the map name for the folder.
    level_folder = os.path.join(base_folder, map_base)

    if DRY_RUN:
        print(f"DRY-RUN: Would create folder: {level_folder}")
    else:
        os.makedirs(level_folder, exist_ok=True)

    # Copy and rename the .wad file.
    src_wad = os.path.join(uya_dir, file_dict['.wad'])
    dst_wad = os.path.join(level_folder, f"level{level_str}.0.wad")
    if DRY_RUN:
        print(f"DRY-RUN: Would copy {src_wad} to {dst_wad}")
    else:
        shutil.copy2(src_wad, dst_wad)

    # Copy and rename the .world file.
    src_world = os.path.join(uya_dir, file_dict['.world'])
    dst_world = os.path.join(level_folder, f"level{level_str}.2.wad")
    if DRY_RUN:
        print(f"DRY-RUN: Would copy {src_world} to {dst_world}")
    else:
        shutil.copy2(src_world, dst_world)

    # Copy unpack.sh from the base folder into the level folder.
    src_unpack = os.path.join(base_folder, unpack_script_name)
    dst_unpack = os.path.join(level_folder, unpack_script_name)
    if DRY_RUN:
        print(f"DRY-RUN: Would copy {src_unpack} to {dst_unpack}")
    else:
        shutil.copy2(src_unpack, dst_unpack)
        # Edit unpack.sh: replace 'LEVEL_ID=XX' with the actual level ID.
        try:
            with open(dst_unpack, 'r') as f:
                content = f.read()
            new_content = re.sub(r'(LEVEL_ID=)XX', r'\g<1>' + str(level_id), content)
            # For logging, find the modified line.
            modified_line = None
            for line in new_content.splitlines():
                if line.startswith("LEVEL_ID="):
                    modified_line = line
                    break
            with open(dst_unpack, 'w') as f:
                f.write(new_content)
            print(f"In '{dst_unpack}': Replaced 'LEVEL_ID=XX' with '{modified_line}'")
        except Exception as e:
            print(f"Error editing '{dst_unpack}': {e}")
            continue

    # Run the shell script inside the level folder.
    # After copying and editing dst_unpack:
    if DRY_RUN:
        print(f"DRY-RUN: Would convert line endings in {dst_unpack} from CRLF to LF")
    else:
        # Convert CRLF (Windows) to LF (Unix) line endings
        try:
            with open(dst_unpack, 'rb') as f:
                content = f.read()
            new_content = content.replace(b'\r\n', b'\n')
            with open(dst_unpack, 'wb') as f:
                f.write(new_content)
            print(f"Converted line endings in {dst_unpack} to Unix format.")
        except Exception as e:
            print(f"Error converting line endings in {dst_unpack}: {e}")
    
    # Then run using WSL
    cmd = ['wsl', './unpack.sh']
    try:
        result = subprocess.run(cmd, cwd=level_folder, shell=True, capture_output=True)
        print(f"Executed unpack.sh in {level_folder} with return code {result.returncode}")
        if result.stdout:
            print("Output:", result.stdout.decode())
        if result.stderr:
            print("Errors:", result.stderr.decode())
    except Exception as e:
        print(f"Error executing unpack.sh in {level_folder}: {e}")
