#!/usr/bin/env python3
"""
sm_tie.py - Decode a TIE render mesh (LOD0) from an in-level GDE blob, split
into per-material triangle groups. (Extracted verbatim from assemble_level.py;
arithmetic unchanged.)

TIE geom, world-local = pos_s16/32768 * GDE_scale * WORLD (then . placement matrix).
WORLD=0.0097 is pinned by the trunk/canopy meshing constraint over 14 trees.

TIE textures: the GDE mesh table (blob + u32(blob+0x14), 20-byte entries) holds a
per-material texture HASH; the LOD0 display list is split into material groups by
GE opcode 0x1D (group k -> material k). Hashes resolve against gim_to_png's
manifest.json (passed in as {hash: entry}).
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

import numpy as np


def parse_groups(d: bytes, strips_off: int, nverts: int) -> List[Tuple[int, List[Tuple[int, int]]]]:
    """Walk the LOD0 display list -> [(matidx, [(strip_start, strip_count)])].
    GE opcode 0x1D opens a new material group; 0x04 (PRIM) is a triangle strip."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    i, vc, mi = strips_off, 0, -1
    groups: List[Tuple[int, List[Tuple[int, int]]]] = []
    while i + 4 <= len(d) and vc < nverts:
        cmd = u32(i); i += 4; op = (cmd >> 24) & 0xFF
        if op == 0x1D:
            mi += 1; groups.append((mi, []))
        elif op == 0x04:
            cnt = cmd & 0xFFFF
            if cnt and groups:
                groups[-1][1].append((vc, cnt)); vc += cnt
    return groups


def decode_tie(d: bytes, blob: int, manifest: Dict[str, dict], world: float):
    """-> (verts Nx3 world-local, uvs Nx2, {matidx: [(a,b,c)]}, [material names])."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    f32 = lambda o: struct.unpack_from("<f", d, o)[0]
    ncount = u32(blob + 0x10); mtab = blob + u32(blob + 0x14)
    mats: List[Optional[str]] = [manifest.get(f"{u32(mtab + k * 20):08x}", {}).get("name")
                                 for k in range(ncount)]
    desc = blob + u32(blob + 0x1C)
    scale = f32(desc + 0x0C); nv = u32(desc + 0x14) // 16; voff = blob + u32(desc + 0x18)
    mb = blob + u32(desc + 0x24); so = blob + u32(mb + 0x08)
    V = np.empty((nv, 3)); UV = np.empty((nv, 2))
    for i in range(nv):
        o = voff + i * 16
        uu, vv = struct.unpack_from("<2h", d, o)
        px, py, pz = struct.unpack_from("<3h", d, o + 0x0A)
        V[i] = (px, py, pz); UV[i] = (uu / 4096.0, vv / 4096.0)
    V = V / 32768.0 * scale * world
    tris: Dict[int, List[Tuple[int, int, int]]] = {k: [] for k in range(max(ncount, 1))}
    for mi, strips in parse_groups(d, so, nv):
        if mi >= ncount:
            continue
        for start, cnt in strips:
            for j in range(cnt - 2):
                a, b, c = start + j, start + j + 1, start + j + 2
                if j % 2:
                    a, b = b, a
                if max(a, b, c) < nv:
                    A, B, C = V[a], V[b], V[c]
                    if np.linalg.norm(np.cross(B - A, C - A)) > 1e-9:
                        tris[mi].append((a, b, c))
    return V, UV, tris, mats
