# Recursivley walk a model directory and read all headers into a dataframe 
import os
import struct
import pandas as pd 
import numpy as np 

class ShrubClassHeader:
    def __init__(self, data):
        self.bounding_sphere = struct.unpack_from('<4f', data, 0x0)  # Vec4f (4 floats starting at 0x10)
        self.mip_distance, = struct.unpack_from('<f', data, 0x10)  # f32 (float at 0x10 + 0x10 = 0x20)
        self.mode_bits, = struct.unpack_from('<H', data, 0x14)  # u16 (2 bytes at 0x14 + 0x10 = 0x24)
        self.instance_count, = struct.unpack_from('<H', data, 0x16)  # s16 (2 bytes at 0x16 + 0x10 = 0x26)
        self.instances_pointer, = struct.unpack_from('<i', data, 0x18)  # s32 (4 bytes at 0x18 + 0x10 = 0x28)
        self.billboard_offset, = struct.unpack_from('<i', data, 0x1c)  # s32 (4 bytes at 0x1c + 0x10 = 0x2c)
        self.scale, = struct.unpack_from('<f', data, 0x20)  # f32 (float at 0x20 + 0x10 = 0x30)
        self.o_class, = struct.unpack_from('<H', data, 0x24)  # s16 (2 bytes at 0x24 + 0x10 = 0x34)
        self.s_class, = struct.unpack_from('<H', data, 0x26)  # s16 (2 bytes at 0x26 + 0x10 = 0x36)
        self.packet_count, = struct.unpack_from('<H', data, 0x28)  # s16 (2 bytes at 0x28 + 0x10 = 0x38)
        self.pad_2a, = struct.unpack_from('<h', data, 0x2a)  # s16 (padding at 0x2a + 0x10 = 0x3a)
        self.normals_offset, = struct.unpack_from('<i', data, 0x2c)  # s32 (4 bytes at 0x2c + 0x10 = 0x3c)
        self.pad_30, = struct.unpack_from('<i', data, 0x30)  # s32 (padding at 0x30 + 0x10 = 0x40)
        self.drawn_count, = struct.unpack_from('<h', data, 0x34)  # s16 (2 bytes at 0x34 + 0x10 = 0x44)
        self.scis_count, = struct.unpack_from('<h', data, 0x36)  # s16 (2 bytes at 0x36 + 0x10 = 0x46)
        self.billboard_count, = struct.unpack_from('<h', data, 0x38)  # s16 (2 bytes at 0x38 + 0x10 = 0x48)
        #self.pad_3a = struct.unpack_from('<3h', data, 0x4a)  # s16[3] (3 shorts at 0x3a + 0x10 = 0x4a)
        self.pad_3a = []
        
    def __repr__(self):
        return (f"head_bytes: {self.head_bytes}, Bounding Sphere: {self.bounding_sphere}, Mip Distance: {self.mip_distance}, Mode Bits: {self.mode_bits}, "
                f"Instance Count: {self.instance_count}, Instances Pointer: {self.instances_pointer}, "
                f"Billboard Offset: {self.billboard_offset}, Scale: {self.scale}, O Class: {self.o_class}, "
                f"S Class: {self.s_class}, Packet Count: {self.packet_count}, Pad 2A: {self.pad_2a}, "
                f"Normals Offset: {self.normals_offset}, Pad 30: {self.pad_30}, Drawn Count: {self.drawn_count}, "
                f"SCIS Count: {self.scis_count}, Billboard Count: {self.billboard_count}, "
                f"Pad 3A: {self.pad_3a}")

def parse_shrub_file(file_path):
    shrubs = []
    with open(file_path, 'rb') as f:
        data = f.read()
        offset = 0
        shrub_size = 0x4C  # Size of one ShrubClassHeader including added padding
        while offset + shrub_size <= len(data):
            shrub = ShrubClassHeader(data[offset:offset + shrub_size])
            shrubs.append(shrub)
            break
            offset += shrub_size
    return shrubs

def shrubs_to_dataframe(shrubs):
    # Create a list of dictionaries where each dictionary is one row of data
    data = []
    for shrub in shrubs:
        data.append({
            "Bounding Sphere": shrub.bounding_sphere,
            "Mip Distance": shrub.mip_distance,
            "Mode Bits": shrub.mode_bits,
            "Instance Count": shrub.instance_count,
            "Instances Pointer": shrub.instances_pointer,
            "Billboard Offset": shrub.billboard_offset,
            "Scale": shrub.scale,
            "O Class": shrub.o_class,
            "S Class": shrub.s_class,
            "Packet Count": shrub.packet_count,
            "Pad 2A": shrub.pad_2a,
            "Normals Offset": shrub.normals_offset,
            "Pad 30": shrub.pad_30,
            "Drawn Count": shrub.drawn_count,
            "SCIS Count": shrub.scis_count,
            "Billboard Count": shrub.billboard_count,
            "Pad 3A": shrub.pad_3a,
        })

    # Convert the list of dictionaries into a DataFrame
    df = pd.DataFrame(data)
    return df

gameplay_shrubs_folder = "H:\\ps2\\packer\\hoven_del\\assets\\shrub"
shrub_bin_files = [os.path.join(root, file) 
               for root, dirs, files in os.walk(gameplay_shrubs_folder) 
               for file in files if file == "shrub.bin"]
s = []
for shrub_bin_file in shrub_bin_files:
    shrubs = parse_shrub_file(shrub_bin_file)
    s.append(shrubs)

# Create an empty list to hold dataframes
dataframes = []
# Loop through each item in the list s and convert to dataframe
for shrub in s:
    df = shrubs_to_dataframe(shrub)
    dataframes.append(df)
# Concatenate all the dataframes into one giant dataframe
dd = pd.concat(dataframes, ignore_index=True)
dd
