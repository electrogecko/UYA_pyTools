import os
import re
import shutil
import subprocess
# This script will scan the base folder for extracted NTSC maps. It will then unpack ...
# ... corresponding PAL maps and put them in a folder named 'pal' 
# Create a ./palextract.sh script which calls packer's extract and points to your pal ISO 
# Point the $PACKER_DIR and $WRENCH_DIR to your Forge Tools folder or the packer CLI 
# Set dry run mode (True means no actual changes, just print what would be done)
DRY_RUN = True

# Set the basee working folder 
base_folder = r'H:\ps2\fix_pal'

pal_folder = os.path.join(base_folder, 'pal')

# Ensure the pal folder exists.
if DRY_RUN:
    print(f"DRY-RUN: Would ensure folder exists: {pal_folder}")
else:
    os.makedirs(pal_folder, exist_ok=True)

# Copy palextract.sh from base_folder into pal_folder so that we can run it.
src_palextract = os.path.join(base_folder, 'palextract.sh')
dst_palextract = os.path.join(pal_folder, 'palextract.sh')
if DRY_RUN:
    print(f"DRY-RUN: Would copy {src_palextract} to {dst_palextract}")
else:
    try:
        shutil.copy2(src_palextract, dst_palextract)
        print(f"Copied palextract.sh to {pal_folder}")
    except Exception as e:
        print(f"Error copying palextract.sh: {e}")

# Compile a list of unpacked levels: folders in base_folder that contain both '00.bin' and 'unpack.sh'
unpacked_levels = []
for entry in os.listdir(base_folder):
    level_path = os.path.join(base_folder, entry)
    if os.path.isdir(level_path):
        file_00 = os.path.join(level_path, '00.bin')
        file_unpack = os.path.join(level_path, 'unpack.sh')
        if os.path.exists(file_00) and os.path.exists(file_unpack):
            unpacked_levels.append(entry)

print("Unpacked Levels found:", unpacked_levels)

# Process each unpacked level
for map_name in unpacked_levels:
    level_path = os.path.join(base_folder, map_name)
    unpack_sh_path = os.path.join(level_path, 'unpack.sh')
    
    # Read unpack.sh to extract the LEVEL_ID using a regex
    try:
        with open(unpack_sh_path, 'r') as f:
            content = f.read()
        m = re.search(r'LEVEL_ID=(\d+)', content)
        if m:
            level_id = m.group(1)
            print(f"Map '{map_name}': Found level ID {level_id}")
        else:
            print(f"Map '{map_name}': Could not extract level ID from {unpack_sh_path}")
            continue
    except Exception as e:
        print(f"Error reading {unpack_sh_path} for map '{map_name}': {e}")
        continue

    # Run the palextract.sh script in the pal folder using WSL.
    # This command should create a folder named "levelXX" inside pal_folder.
    cmd = ['wsl', './palextract.sh', level_id]
    if DRY_RUN:
        print(f"DRY-RUN: Would run command: {' '.join(cmd)} in folder: {pal_folder}")
    else:
        try:
            result = subprocess.run(cmd, cwd=pal_folder, shell=True, capture_output=True)
            print(f"Executed palextract.sh in {pal_folder} with return code {result.returncode}")
            if result.stdout:
                print("Output:", result.stdout.decode())
            if result.stderr:
                print("Errors:", result.stderr.decode())
        except Exception as e:
            print(f"Error executing palextract.sh for map '{map_name}': {e}")
            continue

    # The palextract.sh script creates a folder named "levelXX" in pal_folder.
    # Rename that folder to the map name with '_pal' appended.
    src_extracted_folder = os.path.join(pal_folder, f"level{level_id}")
    dst_extracted_folder = os.path.join(pal_folder, f"{map_name}_pal")
    if DRY_RUN:
        print(f"DRY-RUN: Would rename folder '{src_extracted_folder}' to '{dst_extracted_folder}'")
    else:
        try:
            os.rename(src_extracted_folder, dst_extracted_folder)
            print(f"Renamed folder '{src_extracted_folder}' to '{dst_extracted_folder}'")
        except Exception as e:
            print(f"Error renaming folder '{src_extracted_folder}' to '{dst_extracted_folder}': {e}")
            continue

    # Copy over the master unpack.sh from base_folder into the newly renamed folder,
    # and update it to set LEVEL_ID to the extracted level_id.
    src_master_unpack = os.path.join(base_folder, 'unpack.sh')
    dst_unpack = os.path.join(dst_extracted_folder, 'unpack.sh')
    if DRY_RUN:
        print(f"DRY-RUN: Would copy {src_master_unpack} to {dst_unpack} and update LEVEL_ID to {level_id}")
    else:
        try:
            shutil.copy2(src_master_unpack, dst_unpack)
            # Read the file and update LEVEL_ID=XX to the correct level id.
            with open(dst_unpack, 'r') as f:
                new_content = f.read()
            new_content = re.sub(r'(LEVEL_ID=)XX', r'\g<1>' + level_id, new_content)
            with open(dst_unpack, 'w') as f:
                f.write(new_content)
            print(f"In '{dst_unpack}': Updated LEVEL_ID to {level_id}")
        except Exception as e:
            print(f"Error copying/updating unpack.sh in '{dst_extracted_folder}': {e}")
            continue

    # --- Fix for WSL bash execution: convert CRLF to LF in unpack.sh ---
    if DRY_RUN:
        print(f"DRY-RUN: Would convert line endings in {dst_unpack} from CRLF to LF")
    else:
        try:
            with open(dst_unpack, 'rb') as f:
                content = f.read()
            new_content = content.replace(b'\r\n', b'\n')
            with open(dst_unpack, 'wb') as f:
                f.write(new_content)
            print(f"Converted line endings in {dst_unpack} to Unix format.")
        except Exception as e:
            print(f"Error converting line endings in {dst_unpack}: {e}")

    # Finally, run the unpack.sh command in the newly created folder (using WSL).
    cmd_unpack = ['wsl', './unpack.sh']
    if DRY_RUN:
        print(f"DRY-RUN: Would execute command: {' '.join(cmd_unpack)} in folder: {dst_extracted_folder}")
    else:
        try:
            result = subprocess.run(cmd_unpack, cwd=dst_extracted_folder, shell=True, capture_output=True)
            print(f"Executed unpack.sh in {dst_extracted_folder} with return code {result.returncode}")
            if result.stdout:
                print("Output:", result.stdout.decode())
            if result.stderr:
                print("Errors:", result.stderr.decode())
        except Exception as e:
            print(f"Error executing unpack.sh in '{dst_extracted_folder}': {e}")
