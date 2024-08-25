from PIL import Image
import glob

def invert_colors_with_alpha(image_path):
    image = Image.open(image_path)
    inverted_image = Image.eval(image, lambda x: 255 - x)
    return inverted_image

def invert_colors(image_path):
    image = Image.open(image_path)
    if image.mode == 'RGBA':
        r, g, b, a = image.split()
        r = Image.eval(r, lambda x: 255 - x)
        g = Image.eval(g, lambda x: 255 - x)
        b = Image.eval(b, lambda x: 255 - x)
        inverted_image = Image.merge('RGBA', (r, g, b, a))
    else:
        inverted_image = Image.eval(image, lambda x: 255 - x)
    return inverted_image


def process_images(folder_path):
    image_paths = glob.glob(folder_path + "/tex.*.png")
    for image_path in image_paths:
        inverted_image = invert_colors(image_path)
        inverted_image.save(image_path)
        
        
def invert_bytes(start_address, end_address, file_path):
    with open(file_path, 'rb') as file:
        data = bytearray(file.read())
        for i in range(start_address, end_address + 1):
            if (i - start_address + 1) % 4 != 0:  # Skip every fourth byte
                data[i] = ~data[i] & 0xFF  # Invert the byte

    with open(file_path, 'wb') as file:
        file.write(data)

# Example usage
# start_address = 0x00
# end_address = 0x3FF
def invert_bytes_in_files(start_address, end_address, file_pattern):
    file_paths = glob.glob(file_pattern)
    for file_path in file_paths:
        invert_bytes(start_address, end_address, file_path)
        print(f"Inverted bytes in file: {file_path}")
        
# Fix the horizon and lower sky
def invert_bytes_in_file_offsets(file_path, start_offset, end_offset):
    with open(file_path, 'r+b') as file:
        file.seek(start_offset)
        data = bytearray(file.read(end_offset - start_offset ))

        inverted_data = bytearray(255 - value for value in data)

        file.seek(start_offset)
        file.write(inverted_data)

def invert_bytes_in_file_except_alpha(file_path, start_offset, end_offset):
    with open(file_path, 'r+b') as file:
        file.seek(start_offset)
        data = bytearray(file.read(end_offset - start_offset))

        inverted_data = bytearray(255 - value if (i + 1) % 4 != 0 else value for i, value in enumerate(data))

        file.seek(start_offset)
        file.write(inverted_data)

        
        
def swap_alpha_bytes(file_path, start_offset, end_offset, alpha_value=0):
    with open(file_path, 'rb') as file:
        # Seek to the start offset and read
        file.seek(start_offset)
        byte_data_range = file.read(end_offset - start_offset + 1)

    rgba_values = []
    for i in range(0, len(byte_data_range), 4):
        rgba_values.append((byte_data_range[i], byte_data_range[i+1], byte_data_range[i+2], byte_data_range[i+3]))
    
    alpha_value = 0
    replaced_values = []
    for rgba in rgba_values:
        replaced_values.append(rgba[:3] + (alpha_value,))

    replaced_byte_data = bytearray() # Pack back into bytes 
    for rgba in replaced_values:
        replaced_byte_data.extend(rgba)

    with open(file_path, 'rb+') as file:
        file.seek(start_offset)         # Seek to the start offset again
        file.write(replaced_byte_data)

    return replaced_values

def fill_with_white(file_path, start_offset, end_offset, threshold_r=200, threshold_g=170, threshold_b=150, threshold_a=128):
    with open(file_path, 'r+b') as file:
        file.seek(start_offset)
        data = bytearray(file.read(end_offset - start_offset))

        filled_data = bytearray((threshold_r if i % 4 == 0 else
                                 threshold_g if i % 4 == 1 else
                                 threshold_b if i % 4 == 2 else
                                 threshold_a)
                                for i in range(len(data)))

        file.seek(start_offset)
        file.write(filled_data)
