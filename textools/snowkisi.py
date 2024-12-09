# NOTE: A backup file is used to copy over fresh .palette files before transfomrations. They are set in this script as follows. 
# TODO Import statements in sections. Required imports: glob shutil Path os
# 
# dest_base = r'H:/ps2/packer/kisiv2/'
# stock_base = r'H:/ps2/packer/kisiv2_stock/'

# packer process 
#!/bin/bash
# Define files
#LEVEL_ID=40
#LEVEL_NAME=level$LEVEL_ID
#UNITY_PROJ_DIR="/mnt/c/path/to/Forge/horizon-forge"
#PACKER_DIR=$UNITY_PROJ_DIR/tools/packer/DL.Level.exe
#WRENCH_DIR=$UNITY_PROJ_DIR/tools/wrench/wrenchbuild.exe
#$PACKER_DIR texture -i ./assets/tie -o ./assets/tie -m PNG_FOLDER_TO_ASSET_TEXTURE -r
#$PACKER_DIR pack-world-instance-shrubs -i ./gameplay/shrubs -o ./gameplay -v 3
#$PACKER_DIR pack-world-instance-ties -i ./gameplay/ties -o ./gameplay -v 3
#$PACKER_DIR pack-code -i ./code -o ./00.bin
#$PACKER_DIR pack-gameplay -i ./gameplay -o ./$LEVEL_NAME.2.wad -v 3
#$PACKER_DIR pack-assets -i ./assets -o . -v 3
#$PACKER_DIR pack -i . -o ./$LEVEL_NAME.0.wad
#############################################################################


from pathlib import Path
import shutil
import glob
import os 
import math

metalframe = [
    '02D5\tex.0000.palette',
    '02D6\tex.0000.palette',
]

tie_metal = [ # grav boot middle of bridge
    '19B3', # BRIDGE LIGHT BASE HOLDER
    '19EA', # PIPE UNDER BRIDGE
    '1A58', # SIDES AND WALKWAY OF BRIDGE 
    '1A59\tex.0000.palette', # PIPES FROM BRIDGE TO WATER (WITH LIGHTS) 
    '19F1\tex.0000.palette', # LIGHT AT BASE OF NIP WITH FIXTURE 
    '19F1\tex.0001.palette', # LIGHT AT BASE OF NIP WITH FIXTURE 
    '19F1\tex.0002.palette', # LIGHT AT BASE OF NIP WITH FIXTURE 
    '19F1\tex.0003.palette', # LIGHT AT BASE OF NIP WITH FIXTURE 
    '19F1\tex.0004.palette', # LIGHT AT BASE OF NIP WITH FIXTURE 
    '19B2\tex.0000.palette', # BLUE LIGHT BRIDGE 
    '19B2\tex.0001.palette', # BLUE LIGHT BRIDGE 
    '16EC\tex.0002.palette', # ANTENNA STUB NEAR BASE (HAS TWO STRIPS LIGHTS?)
]
tie_metal_dark =[ # brownish
    '1A55', # BRIDGE PIECE WITH GRAV RAMP (PIECE IS DARKISH) 
    '1A56', # BRIDGE JUST GRAV RAMP 
    '1F19', # VEH PAD
    '1F1F', # NODE CRANK' 
]
#!16D0 amy be problematic and 16CF
tie_lights = [ #19 20 28 29 31 32 44 53 64 92 93 
    '02D5', # RED BASE LIGHT \tex.0001.palette
    '02D6', # BLUE BASE LIGHT \tex.0001.palette
    '19B2\tex.0002.palette', # BLUE LIGHT BRIDGE 
    '19F1\tex.0005.palette', # LIGHT AT BASE OF NIP WITH FIXTURE 
    '1C89\tex.0002.palette', # LIGHTS AT NIP NODES RED WITH ANTENNA BROWN
    '1C89\tex.0003.palette', # LIGHTS AT NIP NODES RED WITH ANTENNA BROWN
    '1731\tex.0001.palette', # Hovership with yellow and blue lights
    '1731\tex.0006.palette', # Hovership with yellow and blue lights
    '1731\tex.0007.palette', # Hovership with yellow and blue lights
    '1728\tex.0000.palette', # FLOATING NODE JETS (YELLOW INSIDE) 
    '16ED\tex.0008.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT


    '16DF\tex.0003.palette', # UNDERPASS HAS YELLOW LIGHTS
    '16DF\tex.0004.palette', # UNDERPASS HAS YELLOW LIGHTS light gradient

    '16DE\tex.0003.palette', # STRIP LIGHT ANTENNA HAS 2 RED DOTS (LIGHTS?)
    '16DE\tex.0004.palette', # STRIP LIGHT ANTENNA HAS 2 RED DOTS (LIGHTS?)
    '16DD\tex.0002.palette', # HOVERSHIP RAIL HAS RED LIGHT
    '16DD\tex.0003.palette', # HOVERSHIP RAIL HAS RED LIGHT
]
tie_sq_light = [ #  24 
    '1A59\tex.0001.palette', # think this is 75 square light
]
tie_base_light = [
    '1D43\tex.0002.palette', # FRONT OF BASE (WITH LIGHTS RED)
    '1D4E\tex.0000.palette', # FRONT OF BASE (WITH LIGHTS BLUE)
    '1D44\tex.0002.palette', #  BASE pANEL  (WITH LIGHTS RED)
    '1D4D\tex.0002.palette', #  BASE pANEL  (WITH LIGHTS BLUE)
]
tie_base = [
    '1D42', # GAT HOLDER AND FIXTURE TO BASE
    '1D43\tex.0000.palette', # FRONT OF BASE (WITH LIGHTS RED)
    '1D43\tex.0001.palette', # FRONT OF BASE (WITH LIGHTS RED)
    '1D43\tex.0003.palette', # FRONT OF BASE (WITH LIGHTS RED)
    '1D43\tex.0004.palette', # FRONT OF BASE (WITH LIGHTS RED)
    '1D4E\tex.0001.palette', # FRONT OF BASE (WITH LIGHTS BLUE)
    '1D4E\tex.0002.palette', # FRONT OF BASE (WITH LIGHTS BLUE)
    '1D4E\tex.0003.palette', # FRONT OF BASE (WITH LIGHTS BLUE)
    '1D44\tex.0000.palette', #  BASE pANEL  (WITH LIGHTS RED)
    '1D44\tex.0001.palette', #  BASE pANEL  (WITH LIGHTS RED)
    '1D4D\tex.0000.palette', #  BASE pANEL  (WITH LIGHTS BLUE)
    '1D4D\tex.0001.palette', #  BASE pANEL  (WITH LIGHTS BLUE)
    #'1D4D\tex.0002.palette', #  BASE pANEL  (WITH LIGHTS BLUE) this is the light part 
    '1D45', #  BASE BOTOM BLOCK
    '1D46', # BASE SIDE PANEL
    '1D47', # BASE CORNER PANEL
    '1D48', # BASE ROOF
    '1D4C', # BASE BACK PANEL
    '1F20', # ANTENNA OF GAT
    '1F21', # HOLDER ARM OF ANTENNA AND GAT
    '1F22', # PIECES OF GAT 
]
tie_grass = [ 
    '1734', # TIE ORANGE TREE 
    '1735', # TIE TREE STUB
]
tie_dirt = [
    '16C5', # CRATER THING
]
tie_brown = [ 
    # '16B4\tex.0000.palette', # bridge piece
    # '16B4\tex.0001.palette', # bridge piece
    # '16B4\tex.0002.palette', # bridge piece
    '16B4',
    '16B7',
    '16BA',
    '16BC',
    # '16C3', # HAS LONG+ STRIP LIGHT IN MIDDLE
    '16C3\tex.0000.palette',
    '16C3\tex.0001.palette',
    '16C3\tex.0002.palette', # this one looks grungy. could be made frosty
    '16C3\tex.0003.palette',
    '16C3\tex.0004.palette',
    '16C3\tex.0005.palette',
    '16C3\tex.0006.palette',
    '16C3\tex.0007.palette',
    '16C3\tex.0008.palette',
    '16C3\tex.0009.palette',
    '16C3\tex.0010.palette',
    #'16C3\tex.0004.palette', # this was 14 disabling......
    '16C4', # NEXT TO STIRP LIGHT
    '16CD', # HOVERHSIP WALL
    '16CE', # HOVERSHIP WALL
    '16CF', # HOVERSHIP WITH STRIP LIGHT
    '16D0', # HOVERSHIP ENTRY PLATE, HAS LIGHT THING
    '16DD\tex.0000.palette', # HOVERSHIP RAIL HAS RED LIGHT
    '16DD\tex.0001.palette', # HOVERSHIP RAIL HAS RED LIGHT
    '16DD\tex.0004.palette', # HOVERSHIP RAIL HAS RED LIGHT
    '16DE\tex.0000.palette', # STRIP LIGHT ANTENNA HAS 2 RED DOTS (LIGHTS?)
    '16DE\tex.0001.palette', # STRIP LIGHT ANTENNA HAS 2 RED DOTS (LIGHTS?)
    '16DE\tex.0002.palette', # STRIP LIGHT ANTENNA HAS 2 RED DOTS (LIGHTS?)

    '16DF\tex.0000.palette', # UNDERPASS HAS YELLOW LIGHTS
    '16DF\tex.0001.palette', # UNDERPASS HAS YELLOW LIGHTS
    '16DF\tex.0002.palette', # UNDERPASS HAS YELLOW LIGHTS
    #####'16DF\tex.0004.palette', # UNDERPASS HAS YELLOW LIGHTS
    '16EC\tex.0000.palette', # ANTENNA STUB NEAR BASE (HAS TWO STRIPS LIGHTS?)
    '16EC\tex.0001.palette', # ANTENNA STUB NEAR BASE (HAS TWO STRIPS LIGHTS?)
    '16EC\tex.0003.palette', # ANTENNA STUB NEAR BASE (HAS TWO STRIPS LIGHTS?)
    '16EC\tex.0005.palette', # ANTENNA STUB NEAR BASE (HAS TWO STRIPS LIGHTS?) !grungy

    '16EC\tex.0004.palette', # ANTENNA STUB NEAR BASE (HAS TWO STRIPS LIGHTS?) disabling....

    
    '16ED\tex.0000.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT
    '16ED\tex.0001.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT
    '16ED\tex.0002.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT
    '16ED\tex.0003.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT 
    '16ED\tex.0004.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT ! pattern
    '16ED\tex.0005.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT
    '16ED\tex.0006.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT
    '16ED\tex.0007.palette', # ANTENNA STUB TOP WITH YELLOW DOT LIGHT ! grey-ish 
    '1728\tex.0001.palette', # FLOATING NODE JETS (YELLOW INSIDE) 
    '1728\tex.0002.palette', # FLOATING NODE JETS (YELLOW INSIDE) 
    '1728\tex.0003.palette', # FLOATING NODE JETS (YELLOW INSIDE) 
    '1728\tex.0004.palette', # FLOATING NODE JETS (YELLOW INSIDE) 
    '1728\tex.0005.palette', # FLOATING NODE JETS (YELLOW INSIDE) 
    '1729', # HOVER PIECE HAS DARKER RIBBED PANEL 
    '1729', # HOVER PIECE ANTENNA JETS DOWN OUT 
    '1729', # HOVER PIECE TOP
   ############## '1721', # Hover piece jutting outward 
    '172A', # Hover piece side out 
    '172B', # Hover piece side out 
    '172C', # HOVER PIECE WITH BLACK PANELS
    '172D', # HOVER PIECE DOWN
    '172E', # HOVER PIECE DOWN
    '172F', # HOVER PIECE DOWN
    '1C89\tex.0000.palette', # LIGHTS AT NIP NODES RED WITH ANTENNA BROWN
    '1C89\tex.0001.palette', # LIGHTS AT NIP NODES RED WITH ANTENNA BROWN
    '1C89\tex.0004.palette', # LIGHTS AT NIP NODES RED WITH ANTENNA BROWN
    '1731\tex.0000.palette', # Hovership with yellow and blue lights
    '1731\tex.0002.palette', # Hovership with yellow and blue lights
    '1731\tex.0003.palette', # Hovership with yellow and blue lights
    '1731\tex.0004.palette', # Hovership with yellow and blue lights
    '1731\tex.0005.palette', # Hovership with yellow and blue lights
]
tie_grungy = [
    '16C3\tex.0002.palette', # this one looks grungy. could be made frosty
    '16EC\tex.0005.palette', # ANTENNA STUB NEAR BASE (HAS TWO STRIPS LIGHTS?) !grungy
]
ter_lights = [
    24,
    33,
    36, # half half
    49, # blue
    50, #blu gradient 
    51 # blue half half 
]
ter_sq_lights = [ 44  ] # like 25, 28 # 47 is the logo near nip top, but it has brown surrounding. 
ter_sq_brownthing = [ 21, 45 ] # like 31,32
ter_grassdirt = [
    41,
    23,
    22,
    18,
    17,
    16,
    15,
    14,
    13, 
    11
]
ter_blusish = [
    25,
    26,

    28,
    29,
    30,
    31,
    32,

    34,

    38,
    39,
    40,

    42,
    43
]
ter_metal  = [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    12,
    19,
    20,
    27, # 52 is ter_metal 
    35, 
    37,
    46,
    48,

    47  # moving this over because it is better here (nip sign) 
]


moby_brown = [
    '1A63/tex.0000.palette',
    '1A63/tex.0001.palette',
    '1A63/tex.0003.palette',

    '15CA/tex.0000.palette',
    '15CA/tex.0001.palette',
   
    '1AD6/tex.0000.palette',
    '1AD6/tex.0003.palette',
    '1AD6/tex.0004.palette',
    '1AD6/tex.0005.palette',
    '1AD6/tex.0007.palette',
    '1AD6/tex.0008.palette',
    '1AD6/tex.0009.palette',
    
]
moby_lights = [
    '1A63/tex.0002.palette'
]
moby_crank = [
    '1A27/tex.0000.palette'
    '1A27/tex.0001.palette'
    '1A27/tex.0002.palette'
    '1A27/tex.0003.palette'
]
ship = [
    '107E/tex.0000.palette'
]
turbo = [
    '107C/tex.0000.palette'
]
ranger = [
    '109E/tex.0000.palette'
    '109F/tex.0000.palette'
]
jumppad = [
    '10C4/tex.0000.palette'
    '10C4/tex.0001.palette'
]
#################%%%%%%%%%%%%%%



def convert_to_palette(numbers):
    palette_list = []
    for num in numbers:
        palette_list.append("tex.{:04d}.palette".format(num))
    return palette_list

ter_lights = convert_to_palette(ter_lights)
ter_sq_lights = convert_to_palette(ter_sq_lights)
ter_sq_brownthing = convert_to_palette(ter_sq_brownthing)
ter_grassdirt = convert_to_palette(ter_grassdirt)
ter_blusish = convert_to_palette(ter_blusish)
ter_metal = convert_to_palette(ter_metal)

import os

def process_palette_files(base_dir, input_list):
    output_list = []
    base_dir = os.path.abspath(base_dir)  # Normalize base directory
    
    for entry in input_list:
        # Normalize the entry by replacing backslashes with forward slashes
        normalized_entry = entry.replace('\\', '/').replace('\t', '/t')  # Handle tab-separated input
        
        if '/' in normalized_entry:
            # Split into folder keyword and relative file path
            try:
                folder_keyword, file_path = normalized_entry.split('/', 1)
            except ValueError:
                print(f"Error: Invalid format in entry '{normalized_entry}'")
                continue
            
            folder_found = False
            for root, dirs, files in os.walk(base_dir):
                if folder_keyword in os.path.basename(root):  # Match folder containing the keyword
                    folder_found = True
                    full_path = os.path.join(root, file_path)
                    if os.path.isfile(full_path):
                        # Add relative path to the output list
                        relative_path = os.path.relpath(full_path, base_dir)
                        output_list.append(relative_path)
                    else:
                        print(f"Warning: File '{file_path}' not found in folder '{root}'")
            if not folder_found:
                print(f"Warning: Folder containing '{folder_keyword}' not found in '{base_dir}'")
        else:
            # Entry is just a folder keyword, find folders containing the keyword and grab all `.palette` files
            folder_found = False
            for root, dirs, files in os.walk(base_dir):
                if normalized_entry in os.path.basename(root):  # Match folder containing the keyword
                    folder_found = True
                    for file_name in files:
                        if file_name.endswith('.palette'):
                            # Add relative path to the output list
                            relative_path = os.path.relpath(os.path.join(root, file_name), base_dir)
                            output_list.append(relative_path)
            if not folder_found:
                print(f"Warning: Folder containing '{normalized_entry}' not found in '{base_dir}'")
    
    return output_list

#import filetools
def darken_colors(folder, pal_list, dimR=0.9, dimG=0.5, dimB=0.7, dimA=1):
    print('Darkening: ' + str(len(pal_list)) + ' files')
    for file_name in pal_list:
        file_path = os.path.join(folder, file_name)

        # Read the bytes from the file
        with open(file_path, "rb") as file:
            byte_data = file.read()

            # Split the byte data into groups of 4 (R, G, B, A)
            groups = [byte_data[i:i+4] for i in range(0, len(byte_data), 4)]

            # Modify RGBA values unless they are all zero
            modified_groups = [
                group if group == b'\x00\x00\x00\x00' else 
                bytes([int(dimR * group[0]), int(dimG * group[1]), int(dimB * group[2]), group[3]])
                for group in groups
            ]

            # Concatenate the modified groups back into byte data
            modified_byte_data = b"".join(modified_groups)

            # Write the modified byte data back to the file
            with open(file_path, "wb") as file:
                file.write(modified_byte_data)


def darken_exponential(folder, pal_list, dimR=0.9, dimG=0.5, dimB=0.7, dimA=1):
    print('Darkening: ' + str(len(pal_list)) + ' files')
    for file_name in pal_list:
        file_path = os.path.join(folder, file_name)

        # Read the bytes from the file
        with open(file_path, "rb") as file:
            byte_data = file.read()

            # Split the byte data into groups of 4 (R, G, B, A)
            groups = [byte_data[i:i+4] for i in range(0, len(byte_data), 4)]

            # Modify RGBA values unless they are all zero
            def adjust_color(value, dim_factor):
                """Adjust color value using exponential darkening."""
                return int(value * math.pow(dim_factor, value / 255))

            modified_groups = [
                group if group == b'\x00\x00\x00\x00' else 
                bytes([
                    adjust_color(group[0], dimR),
                    adjust_color(group[1], dimG),
                    adjust_color(group[2], dimB),
                    int(group[3] * dimA)
                ])
                for group in groups
            ]

            # Concatenate the modified groups 


def brighten_lights(folder, pal_list, alpha=255):
    print('Brightening: ' + str(len(pal_list)) + ' files')
    for file_name in pal_list:
        file_path = os.path.join(folder, file_name)

        # Read the bytes from the file
        with open(file_path, "rb") as file:
            byte_data = file.read()

            # Split the byte data into groups of 4 (R, G, B, A)
            groups = [byte_data[i:i+4] for i in range(0, len(byte_data), 4)]

            # Modify RGBA values unless they are all zero
            modified_groups = [
                group if group == b'\x00\x00\x00\x00' else 
                bytes([group[0], group[1], group[2], alpha])
                for group in groups
            ]

            # Concatenate the modified groups back into byte data
            modified_byte_data = b"".join(modified_groups)

            # Write the modified byte data back to the file
            with open(file_path, "wb") as file:
                file.write(modified_byte_data)

def make_snowy(folder, pal_list):
    print('Making Snowy: ' + str(len(pal_list)) + ' files')
    thresh = 2
    g = 0.6
    for file_name in pal_list:
        file_path = os.path.join(folder, file_name)

        # Read the bytes from the file
        with open(file_path, "rb") as file:
            byte_data = file.read()

            # Split the byte data into groups of 4 (R, G, B, A)
            groups = [byte_data[i:i+4] for i in range(0, len(byte_data), 4)]

            # Modify RGBA values unless they are all zero
            modified_groups = []
            for group in groups:
                if group == b'\x00\x00\x00\x00':
                    modified_groups.append(group)
                elif thresh * group[1] > group[0] + group[2]:
                    modified_groups.append(bytes([
                        int(g * min(group[1] + 95, 255)),
                        int(g * min(group[1] + 95, 255)),
                        int(g * min(group[1] + 110, 255)),
                        group[3]
                    ]))
                else:
                    modified_groups.append(bytes([
                        int(g * group[0]),
                        int(g * group[1]),
                        int(g * group[2]),
                        group[3]
                    ]))

            # Concatenate the modified groups back into byte data
            modified_byte_data = b"".join(modified_groups)

            # Write the modified byte data back to the file
            with open(file_path, "wb") as file:
                file.write(modified_byte_data)
                
def copy_recursive(source_base, dest_base, file_pattern):
    # Walk through each directory in the source base
    for root, dirs, files in os.walk(source_base):
        # Calculate relative path from source base to current directory
        relative_path = os.path.relpath(root, source_base)
        # Create the corresponding destination directory
        dest_dir = os.path.join(dest_base, relative_path)
        os.makedirs(dest_dir, exist_ok=True)
        
        # Find all files matching the pattern in the current directory
        for file in glob.glob(os.path.join(root, file_pattern)):
            # Copy each file to the destination directory
            shutil.copy(file, dest_dir)


# Terrain 
s = 0.7
source_directory =  os.path.join(stock_base, 'assets/terrain')
destination_directory = os.path.join(dest_base, 'assets/terrain')

# Copy over backups 
copy_recursive(source_directory, destination_directory, '*.palette')

# darken_colors(ter_lights, dimR = 0.5, dimG = 0.6, dimB = 0.6, dimA = 1) # lights
# darken_colors(ter_sq_lights, dimR = 0.5, dimG = 0.6, dimB = 0.6, dimA = 1) # square lights
darken_colors(destination_directory,ter_sq_brownthing, dimR = 0.6*s, dimG = 0.6*s, dimB = 0.6*s, dimA = 1) # brown thing
#darken_colors(terrfolder,ter_grassdirt, dimR = 0.6*g, dimG = 0.6*g, dimB = 0.6*g, dimA = 1) # grass/dirt
make_snowy(destination_directory,ter_grassdirt)
darken_colors(destination_directory,ter_blusish, dimR = 0.6*s, dimG = 0.6*s, dimB = 0.6*s, dimA = 1) # blueish
darken_colors(destination_directory,ter_metal, dimR = 0.6*s, dimG = 0.6*s, dimB = 0.6*s, dimA = 1) # metal



# shrub
g = 0.9
source_directory =  os.path.join(stock_base, 'assets/shrub')
destination_directory = os.path.join(dest_base, 'assets/shrub')

# Perform the recursive copy
copy_recursive(source_directory, destination_directory, '*.palette')

# New packer nests shrub folders 
shrub = [os.path.relpath(file, os.path.join(dest_base, 'assets', 'shrub')) 
         for file in glob.glob(os.path.join(dest_base, 'assets', 'shrub', '*', '*.palette'))]

# Define shrubfolder as before
shrubfolder = os.path.join(dest_base, 'assets', 'shrub')

# Call the make_snowy function with the updated shrub list
make_snowy(shrubfolder, shrub)
s = 0.95
#darken_colors(shrubfolder,shrub, dimR = 0.6*s, dimG = 0.6*s, dimB = 0.6*s, dimA = 1) 



# Define source and destination directories for this example
source_directory = os.path.join(stock_base, 'assets/tie')
destination_directory = os.path.join(dest_base, 'assets/tie')

tie_metal = process_palette_files(source_directory,tie_metal)
tie_metal_dark = process_palette_files(source_directory,tie_metal_dark)
tie_lights = process_palette_files(source_directory,tie_lights)
tie_sq_light = process_palette_files(source_directory,tie_sq_light)
tie_base = process_palette_files(source_directory,tie_base)
tie_grass = process_palette_files(source_directory,tie_grass)
tie_dirt = process_palette_files(source_directory,tie_dirt)
tie_brown = process_palette_files(source_directory,tie_brown)
tie_grungy = process_palette_files(source_directory,tie_grungy)
tie_base_light = process_palette_files(source_directory,tie_base_light)

###################%%%%%%%%%%%%%%

# Perform the recursive copy
copy_recursive(source_directory, destination_directory, '*.palette')

# Step 3: Call the make_snowy function
#make_snowy(str(tiefolder), tie_brown_with_dirs)
s = 0.7
r = 0.9
b = 1
g = 0.95
darken_colors(destination_directory, tie_brown, dimR = 0.5*s, dimG = 0.6*s, dimB = 0.6*s, dimA = 1) # Darken the brown 
darken_colors(destination_directory, tie_metal, dimR = 0.7*s, dimG = 0.8*s, dimB = 0.8*s, dimA = 1) # Darken metal 
darken_colors(destination_directory, tie_metal_dark, dimR = 0.7*s, dimG = 0.8*s, dimB = 0.8*s, dimA = 1) # Darken the dark metal
##darken_colors(destination_directory, tie_grass, dimR = 0.5*g, dimG = 0.55*g, dimB = 0.6*g*g, dimA = 1) # darken the grass 
##darken_colors(destination_directory, tie_dirt, dimR = 0.5*g, dimG = 0.6*g, dimB = 0.6*g, dimA = 1) # Darken the dirt
make_snowy(destination_directory, tie_grass)
make_snowy(destination_directory, tie_dirt)

#make_snowy(destination_directory, tie_grungy) # this doesnt look good 

sb=0.85
darken_colors(destination_directory, tie_base, dimR = 0.5*sb, dimG = 0.6*sb, dimB = 0.6*sb, dimA = 1) # Darken the brown 

#darken_colors(destination_directory, tie_dirt, dimR = 0.7*g, dimG = 0.8*g, dimB = 0.8*g, dimA = 1) # Darken the dirt

#for light in tie_lights:
    # brighten_lights(tiefolder,light,254)
brighten_lights(destination_directory,tie_base_light,230)
brighten_lights(destination_directory,tie_lights,254)
print("All tie tex files processed successfully.")
