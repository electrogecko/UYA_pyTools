import os
import struct    # This is the method to inject Xyz into bin file
import binascii  # This will insert a string of binary. 

# def hex2dec(hex_list):
#     decimal_list = []
#     for hex_str in hex_list:
#         decimal_value = int(hex_str, 16)
#         decimal_list.append(decimal_value)
#     return decimal_list
def hex2dec(hex_list):
    decimal_list = []
    for hex_str in hex_list:
        decimal_value = int(hex_str, 16)
        decimal_list.append(decimal_value)
    return decimal_list
def dec2hex(decimal_list):
    hex_list = []
    for decimal_value in decimal_list:
        hex_str = hex(decimal_value)[2:].upper()
        hex_list.append(hex_str)
    return hex_list

def parseXYZ(filename, values_tuple, address, z_override=None):
    try:
        # Override the third value of the tuple if z_override is provided
        if z_override is not None:
            values_tuple = (values_tuple[0], values_tuple[1], z_override)

        # Convert values in the tuple to single precision floats
        floats = [struct.pack('f', value) for value in values_tuple]

        # Join the floats into a binary string
        data = b''.join(floats)

        # Open the file in binary mode for writing
        with open(filename, 'rb+') as file:
            #print('opened file ' + str(file))

            # Seek to the specified address in the file
            file.seek(address)

            # Write the data to the file
            file.write(data)

        # Close the file
        file.close()
        #print('Success writing ' + filename)
    except:
        try: 
            file.close
        except Exception as me:
            print(me)
            print('Failed to write ' + filename)


def parseX(filename, value, address):
    try:
        # Convert values in the tuple to single precision floats
        # Join the floats into a binary string
        data = struct.pack('f', value)

        # Open the file in binary mode for writing
        with open(filename, 'rb+') as file:
            #print('opened file ' + str(file))

            # Seek to the specified address in the file
            file.seek(address)

            # Write the data to the file
            file.write(data)

        # Close the file
        file.close()
        #print('Success writing ' + filename)
    except:
        try: 
            file.close
        except:
            pass
        print('Failed to write ' + filename)

def insert_hex_string(filepath, hex_string, address=None):
    # Convert the hex string to binary data
    hex_data = binascii.unhexlify(hex_string.replace(' ', ''))

    # Open the file in binary read and write mode
    with open(filepath, 'rb+') as file:
        if address is not None:
            # Move the file pointer to the desired address
            file.seek(address)

        # Write the binary data to the file
        file.write(hex_data)
# Example usage
#filepath = 'path/to/your/file.bin'
#address = 0x0C
#hex_string = 'B3 0D 51 44 75 46 C5 43 AA 0B AB 43'
#insert_hex_string(filepath, hex_string, address)

def read_floats_from_file(filepath, num_floats, address):
    # Open the file in binary read mode
    with open(filepath, 'rb') as file:
        # Move the file pointer to the desired address
        file.seek(address)

        # Read the specified number of floats from the file
        floats = []
        for _ in range(num_floats):
            float_bytes = file.read(4)  # Read 4 bytes for each float
            if len(float_bytes) == 4:
                float_value = struct.unpack('f', float_bytes)[0]
                floats.append(float_value)
            else:
                break  # Break if there are not enough bytes remaining in the file

    return floats

def read_uint8_from_file(filepath, num_uint8, address):
    # Open the file in binary read mode
    with open(filepath, 'rb') as file:
        # Move the file pointer to the desired address
        file.seek(address)

        # Read the specified number of uint8 values from the file
        uint8_values = []
        for _ in range(num_uint8):
            uint8_byte = file.read(1)  # Read 1 byte for each uint8 value
            if len(uint8_byte) == 1:
                uint8_value = struct.unpack('B', uint8_byte)[0]
                uint8_values.append(uint8_value)
            else:
                break  # Break if there are not enough bytes remaining in the file

    return uint8_values

def insert_uint8_values(filepath, uint8_values, address=None):
    # Open the file in binary read and write mode
    with open(filepath, 'rb+') as file:
        if address is not None:
            # Move the file pointer to the desired address
            file.seek(address)

        if isinstance(uint8_values, list):
            # Convert the uint8 values to binary data
            uint8_data = struct.pack('B' * len(uint8_values), *uint8_values)
        else:
            # Convert the single uint8 value to binary data
            uint8_data = struct.pack('B', uint8_values)

        # Write the binary data to the file
        file.write(uint8_data)

import os
def search_binary_files(directory, pattern, file_extension='.bin'):
    # Check if the hex_input is already in the proper format  
    fp = []
    mp = []
    if type(pattern)==str:
        pattern = bytes.fromhex(pattern.replace(" ", ""))
        
    if os.path.isdir(directory):
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(file_extension):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'rb') as f:
                        data = f.read()
                        matches = [hex(m.start()) for m in re.finditer(re.escape(pattern), data)]
                        if matches:
                            print(f"Match found in file: {file_path}")
                            print(f"Hex addresses of matches: {', '.join(matches)}")
                        mp.append(matches)
                        fp.append(file_path)

                        # if pattern in data:
                        #     print(f"Match found in file: {file_path}")
                        #     fp.append(file_path)
    else:
        file_path = directory
        with open(file_path, 'rb') as f:
            data = f.read()
            matches = [hex(m.start()) for m in re.finditer(re.escape(pattern), data)]
            if matches:
                print(f"Match found in file: {file_path}")
                print(f"Hex addresses of matches: {', '.join(matches)}")
            fp.append(file_path)
            mp.append(matches)
            # if pattern in data:
                # print(f"Match found in file: {file_path}")
                # fp.append(file_path)
    return fp, mp

# Usage examples:
# search_binary_files('/path/to/directory', '41 00 00 00')
# search_binary_files('/path/to/directory', '41000000', '.txt')  # Providing a different file extension
# search_binary_files('/path/to/directory', '41 00 00 00', '')  # Empty file extension for all files
import re
def get_fname_numbers(file_list):
    numbers = []
    pattern = r'\d+'  # Regular expression pattern to match one or more digits

    for filepath in file_list:
        filename = os.path.basename(filepath)  # Get the filename from the filepath
        matches = re.findall(pattern, filename)  # Find all matches of the pattern in the filename

        for match in matches:
            numbers.append(int(match))  # Convert each match to an integer and add it to the numbers list
    return numbers