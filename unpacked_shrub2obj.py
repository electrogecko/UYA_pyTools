# Export unpacked 
def export_to_obj(parsed_data, filename='output.obj'):
    with open(filename, 'w') as file:
        # Write OBJ header
        file.write("# Exported OBJ file\n")
        
        # Write vertices
        file.write("# Vertices\n")
        for packet in parsed_data['packets']:
            for vertex in packet['vertices']:
                part1 = vertex['part1']
                # Write vertex position in OBJ format (v x y z)
                file.write(f"v {part1.x / 32767.0} {part1.y / 32767.0} {part1.z / 32767.0}\n")

        # Write normals
        file.write("# Normals\n")
        for normal in parsed_data['normals']:
            # Write normal in OBJ format (vn x y z)
            file.write(f"vn {normal.x / 32767.0} {normal.y / 32767.0} {normal.z / 32767.0}\n")
        
        # Optionally, you can add face data if needed (f vertex/texture/normal)
        # Depending on the structure of the parsed data, you could add faces here.
        # Since parsed_data doesn't currently provide face data, we skip that for now.

    print(f"OBJ file '{filename}' has been successfully exported.")

# Example usage
# Assuming parsed_data is available
export_to_obj(parsed_data, filename='output.obj')
