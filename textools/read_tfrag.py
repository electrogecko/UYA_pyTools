import struct
import sys
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class TfragsHeader:
    table_offset: int               # s32
    tfrag_count: int                # s32
    thingy: float                   # f32
    mysterious_second_thingy: int   # u32

@dataclass
class TfragHeader:
    bsphere: Tuple[float, float, float, float]  # Vec4f
    data: int                                   # s32
    lod_2_ofs: int                              # u16
    shared_ofs: int                             # u16
    lod_1_ofs: int                              # u16
    lod_0_ofs: int                              # u16
    tex_ofs: int                                # u16
    rgba_ofs: int                               # u16
    common_size: int                            # u8
    lod_2_size: int                             # u8
    lod_1_size: int                             # u8
    lod_0_size: int                             # u8
    lod_2_rgba_count: int                       # u8
    lod_1_rgba_count: int                       # u8
    lod_0_rgba_count: int                       # u8
    base_only: int                              # u8
    texture_count: int                          # u8
    rgba_size: int                              # u8
    rgba_verts_loc: int                         # u8
    occl_index_stash: int                       # u8
    msphere_count: int                          # u8
    flags: int                                  # u8
    msphere_ofs: int                            # u16
    light_ofs: int                              # u16
    light_end_ofs_rac_gc_uya: int               # u16 (from union)
    dir_lights_one: int                         # u8
    dir_lights_upd: int                         # u8
    point_lights: int                           # u16
    cube_ofs: int                               # u16
    occl_index: int                             # u16
    vert_count: int                             # u8
    tri_count: int                              # u8
    mip_dist: int                               # u16

class Mesh:
    def __init__(self):
        self.vertices: List[Tuple[float, float, float]] = []
        self.faces: List[Tuple[int, int, int]] = []

def read_tfrags_header(f) -> TfragsHeader:
    header_size = 16  # 4 bytes (s32) *2 + 4 bytes (f32) +4 bytes (u32) =16
    header_data = f.read(header_size)
    if len(header_data) < header_size:
        raise ValueError("Unexpected end of file when reading TfragsHeader.")
    
    # Format: <ii f I
    header_format = '<ii f I'
    unpacked = struct.unpack(header_format, header_data)
    
    print(f"Unpacked TfragsHeader: {unpacked}")
    
    return TfragsHeader(
        table_offset=unpacked[0],
        tfrag_count=unpacked[1],
        thingy=unpacked[2],
        mysterious_second_thingy=unpacked[3]
    )

def read_tfrag_header(f) -> TfragHeader:
    # Helper function to read and unpack data
    def read_unpack(fmt, size):
        data = f.read(size)
        if len(data) < size:
            raise ValueError(f"Unexpected end of file when reading {fmt}.")
        return struct.unpack(fmt, data)
    
    # Read bsphere: 4 floats
    bsphere = read_unpack('<4f', 16)
    
    # Read data: s32
    data = read_unpack('<i', 4)[0]
    
    # Read 6 u16 fields
    lod_2_ofs, shared_ofs, lod_1_ofs, lod_0_ofs, tex_ofs, rgba_ofs = read_unpack('<6H', 12)
    
    # Read 11 u8 fields
    (common_size, lod_2_size, lod_1_size, lod_0_size, 
     lod_2_rgba_count, lod_1_rgba_count, lod_0_rgba_count, 
     base_only, texture_count, rgba_size, rgba_verts_loc) = read_unpack('<11B', 11)
    
    # Read occl_index_stash: u8
    occl_index_stash = read_unpack('<B', 1)[0]
    
    # Read msphere_count, flags: 2B
    msphere_count, flags = read_unpack('<2B', 2)
    
    # Read msphere_ofs, light_ofs, light_end_ofs_rac_gc_uya: 3H
    msphere_ofs, light_ofs, light_end_ofs_rac_gc_uya = read_unpack('<3H', 6)
    
    # Read dir_lights_one, dir_lights_upd: 2B
    dir_lights_one, dir_lights_upd = read_unpack('<2B', 2)
    
    # Read point_lights, cube_ofs, occl_index: 3H
    point_lights, cube_ofs, occl_index = read_unpack('<3H', 6)
    
    # Read vert_count, tri_count: 2B
    vert_count, tri_count = read_unpack('<2B', 2)
    
    # Read mip_dist: 1H
    mip_dist = read_unpack('<H', 2)[0]
    
    # Read padding: 2 bytes to reach 64 bytes total
    pad = f.read(2)
    if len(pad) <2:
        raise ValueError("Unexpected end of file when reading padding.")
    
    return TfragHeader(
        bsphere=bsphere,
        data=data,
        lod_2_ofs=lod_2_ofs,
        shared_ofs=shared_ofs,
        lod_1_ofs=lod_1_ofs,
        lod_0_ofs=lod_0_ofs,
        tex_ofs=tex_ofs,
        rgba_ofs=rgba_ofs,
        common_size=common_size,
        lod_2_size=lod_2_size,
        lod_1_size=lod_1_size,
        lod_0_size=lod_0_size,
        lod_2_rgba_count=lod_2_rgba_count,
        lod_1_rgba_count=lod_1_rgba_count,
        lod_0_rgba_count=lod_0_rgba_count,
        base_only=base_only,
        texture_count=texture_count,
        rgba_size=rgba_size,
        rgba_verts_loc=rgba_verts_loc,
        occl_index_stash=occl_index_stash,
        msphere_count=msphere_count,
        flags=flags,
        msphere_ofs=msphere_ofs,
        light_ofs=light_ofs,
        light_end_ofs_rac_gc_uya=light_end_ofs_rac_gc_uya,
        dir_lights_one=dir_lights_one,
        dir_lights_upd=dir_lights_upd,
        point_lights=point_lights,
        cube_ofs=cube_ofs,
        occl_index=occl_index,
        vert_count=vert_count,
        tri_count=tri_count,
        mip_dist=mip_dist
    )


def read_vertices(f, tfrag_header: TfragHeader, tfrag_start_offset: int) -> List[Tuple[float, float, float]]:
    # Calculate shared data offset
    shared_data_offset = tfrag_start_offset + tfrag_header.shared_ofs
    f.seek(shared_data_offset)
    vertex_positions = []
    
    # Assuming common_size represents the count of vertices
    vertex_count = tfrag_header.common_size
    vertex_format = '<3h'  # x, y, z as signed shorts
    vertex_size = struct.calcsize(vertex_format)
    
    print(f"Reading {vertex_count} vertices from offset {shared_data_offset}")
    
    for i in range(vertex_count):
        vertex_data = f.read(vertex_size)
        if len(vertex_data) < vertex_size:
            raise ValueError("Unexpected end of file when reading vertex positions.")
        x, y, z = struct.unpack(vertex_format, vertex_data)
        vertex_positions.append((x / 1024.0, y / 1024.0, z / 1024.0))
    
    return vertex_positions

def read_indices(f, tfrag_header: TfragHeader, tfrag_start_offset: int) -> List[int]:
    indices_offset = tfrag_start_offset + tfrag_header.lod_0_ofs
    f.seek(indices_offset)
    indices_byte_size = tfrag_header.lod_0_size
    indices_count = indices_byte_size // 2  # Assuming u16 indices
    
    print(f"Reading {indices_count} indices from offset {indices_offset}")
    
    indices = []
    for i in range(indices_count):
        index_data = f.read(2)
        if len(index_data) < 2:
            raise ValueError("Unexpected end of file when reading indices.")
        index = struct.unpack('<H', index_data)[0]
        indices.append(index)
    
    return indices

def construct_faces(indices: List[int]) -> List[Tuple[int, int, int]]:
    faces = []
    # Ensure that the number of indices is a multiple of 3
    if len(indices) % 3 != 0:
        print(f"Warning: Number of indices ({len(indices)}) is not a multiple of 3.")
    
    # Iterate over the indices in steps of 3 to form triangles
    for i in range(0, len(indices) - 2, 3):
        v1, v2, v3 = indices[i], indices[i + 1], indices[i + 2]
        faces.append((v1, v2, v3))
    
    return faces



def export_mesh_to_obj(vertices, faces, filename):
    with open(filename, 'w') as f:
        # Write vertices
        for v in vertices:
            f.write(f'v {v[0]} {v[1]} {v[2]}\n')
        # Write faces
        for face in faces:
            # OBJ files are 1-indexed
            f.write(f'f {face[0]+1} {face[1]+1} {face[2]+1}\n')
    print(f"Mesh exported to {filename}")

def visualize_mesh(vertices, faces):
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    # Create a list of face vertices
    mesh = Poly3DCollection([[vertices[idx] for idx in face] for face in faces], alpha=0.5)
    mesh.set_facecolor('cyan')
    ax.add_collection3d(mesh)
    
    # Extract all coordinates for auto-scaling
    all_coords = [coord for vertex in vertices for coord in vertex]
    min_coord = min(all_coords)
    max_coord = max(all_coords)
    
    ax.set_xlim(min_coord, max_coord)
    ax.set_ylim(min_coord, max_coord)
    ax.set_zlim(min_coord, max_coord)
    
    plt.show()

def main():
    # Define path to terrain file here
    input_file = r'H:\ps2\packer\level40\assets\terrain\terrain.bin'
    output_file = 'terrain_mesh.obj'
    
    try:
        with open(input_file, 'rb') as f:
            # Read TfragsHeader
            tfrags_header = read_tfrags_header(f)
            print(f"TfragsHeader: {tfrags_header}")
            
            if tfrags_header.tfrag_count <= 0:
                raise ValueError(f"Invalid tfrag_count: {tfrags_header.tfrag_count}")
            
            # Read Tfrag Headers
            tfrag_headers = []
            f.seek(tfrags_header.table_offset)
            for i in range(tfrags_header.tfrag_count):
                tfrag_start_offset = f.tell()
                try:
                    tfrag_header = read_tfrag_header(f)
                    tfrag_headers.append((tfrag_start_offset, tfrag_header))
                    if i < 3 or i >= tfrags_header.tfrag_count - 3:
                        print(f"Tfrag {i}: Bounding Sphere: {tfrag_header.bsphere}")
                except Exception as e:
                    print(f"Error reading Tfrag {i}: {e}")
                    break
            
            if not tfrag_headers:
                raise ValueError("No TfragHeaders were read successfully.")
            
            # Process the first Tfrag (for simplicity)
            tfrag_start_offset, tfrag_header = tfrag_headers[0]
            print(f"Processing Tfrag 0 at offset {tfrag_start_offset}")
            
            # Read vertices
            vertices = read_vertices(f, tfrag_header, tfrag_start_offset)
            print(f"First Tfrag has {len(vertices)} vertices.")
            
            # Read indices
            indices = read_indices(f, tfrag_header, tfrag_start_offset)
            print(f"First Tfrag has {len(indices)} indices.")
            print(f"First 10 indices: {indices[:10]}")
            
            # Construct faces using the revised function
            faces = construct_faces(indices)
            print(f"First Tfrag has {len(faces)} faces.")
            
            # **New Print Statements**
            print(f"Vertices: {vertices}")
            print(f"Faces: {faces}")
            
            # Export mesh
            #export_mesh_to_obj(vertices, faces, output_file)
    
    except FileNotFoundError:
        print(f"Input file not found: {input_file}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == '__main__':
    main()
