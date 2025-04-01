import os
import re
import shutil
import subprocess

# Set base folder accordingly. This script expects a pal folder to exist
# The script will copy over 00.bin and repack. 
# After pack, it will move over associated level files 
base_folder = r'H:\ps2\fix_pal'

# Dry-run flag: if True, only print the operations, do not perform them.
DRY_RUN = True
output_scan_dir = ''  # todo, move this to a uya folder 

pal_folder = os.path.join(base_folder, 'pal')
output_scan_dir = os.path.join(base_folder, output_scan_dir)

# Verify the pal folder exists.
if not os.path.isdir(pal_folder):
    print(f"Pal folder not found: {pal_folder}")
    exit(1)

# Find pal maps (folders ending with '_pal') in the pal folder.
pal_maps = [d for d in os.listdir(pal_folder) 
            if os.path.isdir(os.path.join(pal_folder, d)) and d.endswith('_pal')]

print("Pal maps found:", pal_maps)

for pal_map in pal_maps:
    # Derive matching output level folder by removing '_pal'
    base_map_name = pal_map[:-4]  # remove the last 4 characters ('_pal')
    output_level_dir = os.path.join(output_scan_dir, base_map_name)
    
    if not os.path.isdir(output_level_dir):
        print(f"Output level folder not found for '{base_map_name}' in {output_scan_dir}")
        continue

    # -------------------------------------------
    # 1. Copy 00.bin from pal folder to output folder.
    # -------------------------------------------
    src_00 = os.path.join(pal_folder, pal_map, '00.bin')
    dst_00 = os.path.join(output_level_dir, '00.bin')
    if DRY_RUN:
        print(f"DRY-RUN: Would copy '{src_00}' to '{dst_00}'")
    else:
        if os.path.exists(src_00):
            shutil.copy2(src_00, dst_00)
            print(f"Copied '{src_00}' to '{dst_00}'")
        else:
            print(f"Source 00.bin not found in {os.path.join(pal_folder, pal_map)}")
    
    # -------------------------------------------
    # 2. Copy pack.sh into the output folder and update LEVEL_ID.
    # -------------------------------------------
    src_pack = os.path.join(base_folder, 'pack.sh')
    dst_pack = os.path.join(output_level_dir, 'pack.sh')
    if DRY_RUN:
        print(f"DRY-RUN: Would copy '{src_pack}' to '{dst_pack}' and update LEVEL_ID")
    else:
        try:
            shutil.copy2(src_pack, dst_pack)
            # Read the local unpack.sh in the output folder to extract LEVEL_ID.
            unpack_sh_path = os.path.join(output_level_dir, 'unpack.sh')
            if os.path.exists(unpack_sh_path):
                with open(unpack_sh_path, 'r') as f:
                    unpack_content = f.read()
                m = re.search(r'LEVEL_ID=(\d+)', unpack_content)
                if m:
                    level_id = m.group(1)
                    # Update the copied pack.sh to set the correct LEVEL_ID.
                    with open(dst_pack, 'r') as f:
                        pack_content = f.read()
                    new_pack_content = re.sub(r'(LEVEL_ID=)XX', r'\g<1>' + level_id, pack_content)
                    with open(dst_pack, 'w') as f:
                        f.write(new_pack_content)
                    print(f"Updated '{dst_pack}' with LEVEL_ID {level_id}")
                else:
                    print(f"Could not extract LEVEL_ID from '{unpack_sh_path}'")
            else:
                print(f"'unpack.sh' not found in '{output_level_dir}' to extract LEVEL_ID")
        except Exception as e:
            print(f"Error processing pack.sh in '{output_level_dir}': {e}")

    # -------------------------------------------
    # 3. Execute pack.sh in the output folder using WSL.
    #     (Convert CRLF to LF to fix the ^M error.)
    # -------------------------------------------
    if DRY_RUN:
        print(f"DRY-RUN: Would convert line endings in {dst_pack} from CRLF to LF")
    else:
        try:
            with open(dst_pack, 'rb') as f:
                pack_content_bytes = f.read()
            new_pack_content_bytes = pack_content_bytes.replace(b'\r\n', b'\n')
            with open(dst_pack, 'wb') as f:
                f.write(new_pack_content_bytes)
            print(f"Converted line endings in {dst_pack} to Unix format.")
        except Exception as e:
            print(f"Error converting line endings in {dst_pack}: {e}")
            
    cmd_pack = ['wsl', './pack.sh']
    if DRY_RUN:
        print(f"DRY-RUN: Would execute command: {' '.join(cmd_pack)} in folder: {output_level_dir}")
    else:
        try:
            result = subprocess.run(cmd_pack, cwd=output_level_dir, shell=True, capture_output=True)
            print(f"Executed pack.sh in {output_level_dir} with return code {result.returncode}")
            if result.stdout:
                print("Output:", result.stdout.decode())
            if result.stderr:
                print("Errors:", result.stderr.decode())
        except Exception as e:
            print(f"Error executing pack.sh in '{output_level_dir}': {e}")
    
    # -------------------------------------------
    # 4. Rename level.0.wad and level.2.wad to mapname.wad and mapname.world.
    # -------------------------------------------
    src_wad = os.path.join(output_level_dir, 'level.0.wad')
    src_world = os.path.join(output_level_dir, 'level.2.wad')
    dst_wad = os.path.join(output_level_dir, f"{base_map_name}.wad")
    dst_world = os.path.join(output_level_dir, f"{base_map_name}.world")
    
    if DRY_RUN:
        print(f"DRY-RUN: Would rename '{src_wad}' to '{dst_wad}' and '{src_world}' to '{dst_world}'")
    else:
        try:
            if os.path.exists(src_wad):
                os.rename(src_wad, dst_wad)
                print(f"Renamed '{src_wad}' to '{dst_wad}'")
            else:
                print(f"Source file '{src_wad}' not found.")
            if os.path.exists(src_world):
                os.rename(src_world, dst_world)
                print(f"Renamed '{src_world}' to '{dst_world}'")
            else:
                print(f"Source file '{src_world}' not found.")
        except Exception as e:
            print(f"Error renaming files in '{output_level_dir}': {e}")
    
    # -------------------------------------------
    # 5. Move the renamed files to a new folder: base_folder + 'pal_outputs'.
    # -------------------------------------------
    pal_outputs = os.path.join(base_folder, 'pal_outputs')
    if DRY_RUN:
        print(f"DRY-RUN: Would ensure output folder exists: {pal_outputs}")
    else:
        os.makedirs(pal_outputs, exist_ok=True)
    
    if DRY_RUN:
        print(f"DRY-RUN: Would move '{dst_wad}' and '{dst_world}' from '{output_level_dir}' to '{pal_outputs}'")
    else:
        try:
            if os.path.exists(dst_wad):
                shutil.move(dst_wad, os.path.join(pal_outputs, os.path.basename(dst_wad)))
                print(f"Moved '{dst_wad}' to '{pal_outputs}'")
            else:
                print(f"File '{dst_wad}' not found for moving.")
            if os.path.exists(dst_world):
                shutil.move(dst_world, os.path.join(pal_outputs, os.path.basename(dst_world)))
                print(f"Moved '{dst_world}' to '{pal_outputs}'")
            else:
                print(f"File '{dst_world}' not found for moving.")
        except Exception as e:
            print(f"Error moving files to '{pal_outputs}': {e}")
    
    # -------------------------------------------
    # 6. Copy over the .version, .map, .bg, and .sound files from the UYA folder.
    #     These files are assumed to be named as <mapname>.<ext> and are in the UYA folder.
    # -------------------------------------------
    uya_folder = os.path.join(base_folder, 'uya')
    exts = ['.version', '.map', '.bg', '.sound']
    for ext in exts:
        src_file = os.path.join(uya_folder, base_map_name + ext)
        if os.path.exists(src_file):
            dst_file = os.path.join(pal_outputs, base_map_name + ext)
            if DRY_RUN:
                print(f"DRY-RUN: Would copy '{src_file}' to '{dst_file}'")
            else:
                try:
                    shutil.copy2(src_file, dst_file)
                    print(f"Copied '{src_file}' to '{dst_file}'")
                except Exception as e:
                    print(f"Error copying '{src_file}' to '{dst_file}': {e}")
        else:
            print(f"File '{src_file}' not found in UYA folder.")




# Ensure the destination folder exists (or print what would be done).
if DRY_RUN:
    print(f"DRY-RUN: Would ensure output folder exists: {pal_outputs}")
else:
    os.makedirs(pal_outputs, exist_ok=True)

# Get a list of map folders in the output_scan_dir.
map_folders = [d for d in os.listdir(output_scan_dir) if os.path.isdir(os.path.join(output_scan_dir, d))]
print("Map folders found in output_scan_dir:", map_folders)

for map_folder in map_folders:
    folder_path = os.path.join(output_scan_dir, map_folder)
    
    # Look for files matching the patterns: levelXX.0.wad and levelXX.2.wad (case insensitive)
    wad0 = None
    wad2 = None
    for f in os.listdir(folder_path):
        if re.match(r'level\d{2}\.0\.wad$', f, re.IGNORECASE):
            wad0 = f
        if re.match(r'level\d{2}\.2\.wad$', f, re.IGNORECASE):
            wad2 = f
    
    if not wad0:
        print(f"File matching 'levelXX.0.wad' not found in {folder_path}")
    else:
        src_wad0 = os.path.join(folder_path, wad0)
        new_wad0 = f"{map_folder}.wad"
        dst_wad0 = os.path.join(pal_outputs, new_wad0)
        if DRY_RUN:
            print(f"DRY-RUN: Would rename '{src_wad0}' to '{dst_wad0}'")
        else:
            shutil.copyfile(src_wad0, dst_wad0)
            print(f"Renamed '{src_wad0}' to '{dst_wad0}'")
    
    if not wad2:
        print(f"File matching 'levelXX.2.wad' not found in {folder_path}")
    else:
        src_wad2 = os.path.join(folder_path, wad2)
        new_wad2 = f"{map_folder}.world"
        dst_wad2 = os.path.join(pal_outputs, new_wad2)
        if DRY_RUN:
            print(f"DRY-RUN: Would rename '{src_wad2}' to '{dst_wad2}'")
        else:
            shutil.copyfile(src_wad2, dst_wad2)
            print(f"Renamed '{src_wad2}' to '{dst_wad2}'")
