# Read pvar.bin and view relevant properties in a dataFrame 

import os
import struct
import pandas as pd

# Define the structure offsets in .pvar files
PVAR_OFFSETS = {
    "health_float": 0x030,
    "health": 0x034,
    "turret_damage": 0x234,
    "fire_rate": 0x238,
    "unk_def_75": 0x23C,    # Updated offset for unk_Def_75
    "turret_range": 0x250,  # Float as per the update
    "byte_24C": 0x24C       # Byte 24C for 1A63 directories
}

# Function to search for directories with '1A63' and '1C57' tags
def find_files(root_dir, dir_tag, file_extension='pvar.bin'):
    """Finds all 'pvar.bin' files in directories containing '1A63' or '1C57'."""
    files_data = []
    for dirpath, _, filenames in os.walk(root_dir):
        if dir_tag in dirpath:
            for filename in filenames:
                if filename.endswith(file_extension):
                    pvar_file = os.path.join(dirpath, filename)
                    files_data.append(pvar_file)
                    
    return files_data

# Function to read the turret-related data (for 1A63 directories)
def read_1A63_pvar_data(pvar_file):
    """Reads turret stats and byte 24C from 1A63 'pvar.bin' files."""
    with open(pvar_file, 'rb') as f:
        # Read turret-related values
        f.seek(PVAR_OFFSETS['health_float'])
        health_float = struct.unpack('f', f.read(4))[0]
        
        f.seek(PVAR_OFFSETS['health'])
        health = struct.unpack('H', f.read(2))[0]
        
        f.seek(PVAR_OFFSETS['turret_damage'])
        turret_damage = struct.unpack('I', f.read(4))[0]
        
        f.seek(PVAR_OFFSETS['fire_rate'])
        fire_rate = struct.unpack('I', f.read(4))[0]
        
        f.seek(PVAR_OFFSETS['turret_range'])
        turret_range = struct.unpack('f', f.read(4))[0]  # Updated to float
        
        f.seek(PVAR_OFFSETS['unk_def_75'])
        unk_def_75 = struct.unpack('f', f.read(4))[0]  # New field at 0x43C
        
        f.seek(PVAR_OFFSETS['byte_24C'])
        byte_24C = struct.unpack('B', f.read(1))[0]  # Read byte at offset 24C

    return {
        "health_float": health_float,
        "health": health,
        "turret_damage": turret_damage,
        "fire_rate": fire_rate,
        "turret_range": turret_range,
        "unk_def_75": unk_def_75,
        "byte_24C": byte_24C
    }

# Function to read the byte at 0x8C (for 1C57 directories)
def read_1C57_byte_0x8C(pvar_file):
    """Reads byte 0x8C from 'pvar.bin' files in 1C57 directories."""
    with open(pvar_file, 'rb') as f:
        f.seek(0x8C)
        byte_8C = struct.unpack('B', f.read(1))[0]  # Read 1 byte at offset 0x8C
    return byte_8C

# Main function to process both 1A63 and 1C57 directories and match the values
def process_and_match_files_to_df(root_dir):
    # Find files in directories tagged '1A63' and '1C57'
    pvar_1A63_files = find_files(root_dir, '1A63')
    pvar_1C57_files = find_files(root_dir, '1C57')
    
    results = []
    turret_id = 1  # Start assigning turret IDs
    
    # Read and store byte 0x8C values from 1C57 files
    byte_8C_values = []
    for pvar_file in pvar_1C57_files:
        byte_8C = read_1C57_byte_0x8C(pvar_file)
        byte_8C_values.append(byte_8C)
    
    # Process 1A63 files, read turret-related data and check against all byte 0x8C
    for pvar_file in pvar_1A63_files:
        pvar_data = read_1A63_pvar_data(pvar_file)
        
        # Check if any byte_8C matches byte_24C
        byte_24C = pvar_data['byte_24C']
        matches = [byte_24C == byte_8C for byte_8C in byte_8C_values]
        matches_any = any(matches)  # Check if any match is True
        
        # Collect the data for each turret
        results.append({
            "turret_id": turret_id,
            "health_float": pvar_data['health_float'],
            "health": pvar_data['health'],
            "turret_damage": pvar_data['turret_damage'],
            "fire_rate": pvar_data['fire_rate'],
            "turret_range": pvar_data['turret_range'],
            "unk_def_75": pvar_data['unk_def_75'],
            "byte_24C": byte_24C,
            "matches_any": 'Yes' if matches_any else 'No',
            "matching_byte_8C_values": [byte_8C for i, byte_8C in enumerate(byte_8C_values) if matches[i]]  # List of matching 1C57 entries
        })
        
        turret_id += 1  # Increment turret ID for the next turret

    # Create a DataFrame from the results
    df = pd.DataFrame(results)
    return df

# Example usage
if __name__ == "__main__":
    root_directory = r'H:\ps2\packer\valix44\gameplay\moby'
    df_turrets = process_and_match_files_to_df(root_directory)
    # Display the dataframe in the notebook
    display(df_turrets)
