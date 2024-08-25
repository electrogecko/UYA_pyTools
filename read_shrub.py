# Tested on Packer Version "DL.Level 1.0.0+8d41367f398c777a062083aac525f440a7409ab6"
# Reads unpacked shrub asset model 'shrub.bin' 

import struct

class ShrubClassHeader:
    def __init__(self, data):
        unpacked = struct.unpack('4f f H h I I f h h h I h h h', data)
        self.bounding_sphere = unpacked[:4]
        self.mip_distance = unpacked[4]
        self.mode_bits = unpacked[5]
        self.instance_count = unpacked[6]
        self.instances_pointer = unpacked[7]
        self.billboard_offset = unpacked[8]
        self.scale = unpacked[9]
        self.o_class = unpacked[10]
        self.s_class = unpacked[11]
        self.packet_count = unpacked[12]
        self.normals_offset = unpacked[13]
        self.drawn_count = unpacked[14]
        self.scis_count = unpacked[15]
        self.billboard_count = unpacked[16]

    def __repr__(self):
        return (f"ShrubClassHeader(bounding_sphere={self.bounding_sphere}, "
                f"mip_distance={self.mip_distance}, mode_bits={self.mode_bits}, "
                f"instance_count={self.instance_count}, scale={self.scale}, "
                f"packet_count={self.packet_count}, normals_offset={self.normals_offset}, "
                f"drawn_count={self.drawn_count}, scis_count={self.scis_count}, "
                f"billboard_count={self.billboard_count})")

class ShrubPacketHeader:
    def __init__(self, data):
        self.texture_count, self.gif_tag_count, self.vertex_count, self.vertex_offset = struct.unpack('4I', data)
    
    def __repr__(self):
        return (f"ShrubPacketHeader(texture_count={self.texture_count}, gif_tag_count={self.gif_tag_count}, "
                f"vertex_count={self.vertex_count}, vertex_offset={self.vertex_offset})")

class ShrubPacketEntry:
    def __init__(self, data):
        self.offset, self.size = struct.unpack('2i', data)

    def __repr__(self):
        return f"ShrubPacketEntry(offset={self.offset}, size={self.size})"

class ShrubVertexPart1:
    def __init__(self, data):
        self.x, self.y, self.z, self.gs_packet_offset = struct.unpack('4h', data)
    
    def __repr__(self):
        return f"ShrubVertexPart1(x={self.x}, y={self.y}, z={self.z}, gs_packet_offset={self.gs_packet_offset})"

class ShrubVertexPart2:
    def __init__(self, data):
        self.s, self.t, self.h, self.n_and_stop_cond = struct.unpack('4h', data)
    
    def __repr__(self):
        return f"ShrubVertexPart2(s={self.s}, t={self.t}, h={self.h}, n_and_stop_cond={self.n_and_stop_cond})"

class ShrubNormal:
    def __init__(self, data):
        self.x, self.y, self.z, self.pad = struct.unpack('4h', data)
    
    def __repr__(self):
        return f"ShrubNormal(x={self.x}, y={self.y}, z={self.z}, pad={self.pad})"

def parse_shrub_class(file_path, enable_prints=True):
    with open(file_path, 'rb') as f:
        # Read the entire file into memory
        file_data = f.read()

    # Store parsed data in a structured format
    parsed_data = {
        'header': None,
        'packet_headers': [],
        'packet_entries': [],
        'packets': [],
        'normals': []
    }

    def print_if_enabled(message):
        if enable_prints:
            print(message)

    # Initial offset to start reading from
    current_offset = 0

    # Parse ShrubClassHeader (first 54 bytes)
    shrub_header = ShrubClassHeader(file_data[current_offset:current_offset + 54])
    parsed_data['header'] = shrub_header
    current_offset += 54
    print_if_enabled(shrub_header)

    # Fixed offset for packet headers: assumed to be at 0x40
    packet_header_offset = 0x40

    # Read the first ShrubPacketHeader (16 bytes)
    first_packet_header = ShrubPacketHeader(file_data[packet_header_offset:packet_header_offset + 16])
    parsed_data['packet_headers'].append(first_packet_header)
    print_if_enabled(first_packet_header)

    # Calculate the offset for the packet entries
    packet_entries_offset = packet_header_offset + 16

    # Parse ShrubPacketEntries based on packet count in ShrubClassHeader
    for i in range(shrub_header.packet_count):
        entry_offset = packet_entries_offset + (i * 8)  # Each packet entry is 8 bytes
        packet_entry = ShrubPacketEntry(file_data[entry_offset:entry_offset + 8])
        parsed_data['packet_entries'].append(packet_entry)
        print_if_enabled(f"Packet Entry {i}: {packet_entry}")

    # For each packet entry, read all vertices
    for i, packet_entry in enumerate(parsed_data['packet_entries']):
        packet_data_dict = {
            'vertices': [],
        }
        if packet_entry.size > 0:
            # Calculate absolute offset for the packet's data
            packet_data_offset = packet_entry.offset
            packet_data = file_data[packet_data_offset:packet_data_offset + packet_entry.size]

            print_if_enabled(f"\nParsing Packet {i} for Vertices:")

            vertex_offset = 0
            vertex_index = 0
            try:
                # Loop through vertices in the packet
                while vertex_offset + 16 <= len(packet_data):
                    # Parse ShrubVertexPart1 (first 8 bytes)
                    vertex_part1 = ShrubVertexPart1(packet_data[vertex_offset:vertex_offset + 8])
                    print_if_enabled(f"Packet {i} Vertex {vertex_index} Part 1: {vertex_part1}")

                    # Parse ShrubVertexPart2 (next 8 bytes)
                    vertex_part2 = ShrubVertexPart2(packet_data[vertex_offset + 8:vertex_offset + 16])
                    print_if_enabled(f"Packet {i} Vertex {vertex_index} Part 2: {vertex_part2}")

                    # Add the vertex to the packet's vertices list
                    packet_data_dict['vertices'].append({
                        'part1': vertex_part1,
                        'part2': vertex_part2
                    })

                    # Move to the next vertex (each vertex takes 16 bytes)
                    vertex_offset += 16
                    vertex_index += 1

            except struct.error as e:
                print_if_enabled(f"Error parsing vertex in Packet {i}, moving to next packet. Error: {e}")

        parsed_data['packets'].append(packet_data_dict)

    # Parse normals if normals_offset is valid
    if shrub_header.normals_offset > 0:
        normals_offset = shrub_header.normals_offset
        print_if_enabled("\nParsing Normals:")

        try:
            while normals_offset + 8 <= len(file_data):
                normal_data = file_data[normals_offset:normals_offset + 8]
                normal = ShrubNormal(normal_data)
                parsed_data['normals'].append(normal)
                print_if_enabled(f"Normal: {normal}")
                normals_offset += 8

        except IndexError:
            print_if_enabled("Reached EOF while parsing normals.")

    return parsed_data

if __name__ == "__main__":
    # Example usage: point to absolute path to shrub file, using  
    file_path = r'H:\ps2\packer\level46\assets\shrub\08742_2226\shrub.bin'
    parsed_data = parse_shrub_class(file_path, enable_prints=True)
