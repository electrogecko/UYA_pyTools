import struct
import sys

# Constants
HEADER_SIZE = 0x48

# Offsets within header
OFF = {
    'submesh_table': 0x00,
    'mesh_info': 0x04,     # 4 bytes: high_lod, low_lod, metal_count, metal_begin
    'joint_count': 0x08,
    'unknown_9': 0x09,
    'rac1_byte_a': 0x0A,
    'rac12_byte_b': 0x0B,
    'sequence_count': 0x0C,
    'sound_count': 0x0D,
    'lod_trans': 0x0E,
    'shadow': 0x0F,
    'collision': 0x10,      # s32
    'skeleton': 0x14,       # s32
    'common_trans': 0x18,   # s32
    'joints': 0x1C,         # s32
    'gif_usage': 0x20,      # s32
    'scale': 0x24,          # f32
    'sound_defs': 0x28,     # s32
    'bangles': 0x2C,        # u8
    'mip_dist': 0x2D,       # u8
    'corncob': 0x2E,        # s16
    'bounding_sphere': 0x30,# 4 * f32
    'glow_rgba': 0x40,      # s32
    'mode_bits': 0x44,      # s16
    'type': 0x46,           # u8
    'mode_bits2': 0x47      # u8
}


def read_moby_header(path):
    with open(path, 'rb') as f:
        data = f.read(HEADER_SIZE)

    # Parse
    header = {}
    header['submesh_table_offset'] = struct.unpack_from('<i', data, OFF['submesh_table'])[0]
    header['mesh_info'] = dict(zip(
        ['high_lod', 'low_lod', 'metal_count', 'metal_begin'],
        struct.unpack_from('<4B', data, OFF['mesh_info'])
    ))
    header['joint_count'], header['unknown_9'], header['rac1_byte_a'], header['rac12_byte_b'], \
    header['sequence_count'], header['sound_count'] = struct.unpack_from('<6B', data, OFF['joint_count'])
    header['lod_trans'], header['shadow'] = struct.unpack_from('<2B', data, OFF['lod_trans'])
    header['collision_offset'], header['skeleton_offset'], header['common_trans_offset'], header['joints_offset'] = \
        struct.unpack_from('<4i', data, OFF['collision'])
    header['gif_usage_offset'] = struct.unpack_from('<i', data, OFF['gif_usage'])[0]
    header['scale'] = struct.unpack_from('<f', data, OFF['scale'])[0]
    header['sound_defs_offset'] = struct.unpack_from('<i', data, OFF['sound_defs'])[0]
    header['bangles_offset'], header['mip_dist'] = struct.unpack_from('<2B', data, OFF['bangles'])
    header['corncob_index'] = struct.unpack_from('<h', data, OFF['corncob'])[0]
    header['bounding_sphere'] = struct.unpack_from('<4f', data, OFF['bounding_sphere'])
    header['glow_rgba'] = struct.unpack_from('<i', data, OFF['glow_rgba'])[0]
    header['mode_bits'] = struct.unpack_from('<h', data, OFF['mode_bits'])[0]
    header['type'], header['mode_bits2'] = struct.unpack_from('<2B', data, OFF['type'])

    return header



path = r'H:\ps2\fix3_pal\unpacked_hot\level2\newcar\moby.bin'
hdr = read_moby_header(path)

print("=== MobyClassHeader ===")
for k, v in hdr.items():
    print(f"{k:25}: {v}")

# Read sequence offsets
seq_count = hdr['sequence_count']
if seq_count > 0:
    print(f"\nFound {seq_count} sequence offsets at 0x48:")
    with open(path, 'rb') as f:
        f.seek(0x48)
        seq_data = f.read(4 * seq_count)
    seq_offsets = struct.unpack(f'<{seq_count}i', seq_data)
    for i, ofs in enumerate(seq_offsets):
        print(f"  seq[{i}] @ 0x{ofs:08X}")

# You can extend this to read collision, skeleton, common_trans, joints, sound_defs, etc.
# --- Override `scale` field and write back ---
if False:
    new_scale = 0.07688206434249878
    with open(path, 'r+b') as f:
        f.seek(OFF['scale'])
        f.write(struct.pack('<f', new_scale))
    hdr['scale'] = new_scale
    print(f"\nOverrode scale at offset 0x{OFF['scale']:02X} to {new_scale}")
