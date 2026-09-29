#!/usr/bin/env python3
"""
sm_terrain.py - Decode a STATIC/terrain GDE into per-submesh textured
primitives, in verified native world coords. (Extracted verbatim from
assemble_level.py; arithmetic unchanged.)

TERRAIN world = pos_s16 / 4096 * 14.7687   (anchor/radius = cull sphere, not a
transform). UV divisor is overridable: /2048 tiles seamlessly across chunk
boundaries for the smooth ground textures (rock01 etc.: 0 seams); /4096 leaves a
half-tile offset at chunk seams.

Run standalone to export a terrain-only textured GLB:
  python3 sm_terrain.py terrain.gde --png <gim_to_png dir> -o terrain.glb [--terrain-uv-div 2048]
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

TERR_SCALE = 14.7687
TERR_QUANT = 4096.0


def _strips(d: bytes, off: int, nbytes: int, budget: int) -> List[int]:
    """Terrain strip list: collect GE PRIM (opcode 0x04) vertex counts up to budget."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    counts: List[int] = []; i = off; end = off + max(nbytes, 4); tot = 0
    while i + 4 <= min(end, len(d)) and tot < budget:
        cmd = u32(i); i += 4
        if (cmd >> 24) & 0xFF == 0x04:
            c = cmd & 0xFFFF
            if c:
                counts.append(c); tot += c
    return counts


def decode_terrain(d: bytes, manifest: Dict[str, dict], uv_div: float,
                   scale: float = TERR_SCALE, quant: float = TERR_QUANT):
    """-> (allV, allUV, allT, allM): per-submesh verts (Nx3), uvs (Nx2), tri list,
    and texture-name (or None). uv_div is the terrain UV divisor (4096 or 2048)."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    u16 = lambda o: struct.unpack_from("<H", d, o)[0]
    arr = u32(0x1C); nsub = u32(arr + 0x10)
    subs = [u32(arr + 0x1C + i * 8 + 4) for i in range(nsub)]
    mtab = u32(0x14)
    hashes = [f"{u32(mtab + i * 20):08x}" for i in range(u32(0x10))]
    allV, allUV, allT, allM = [], [], [], []
    for si, so in enumerate(subs):
        V, UV, T = [], [], []
        if so:
            nch = u16(so + 2); co = u32(so + 4)
            for _ in range(nch):
                if co + 0x28 > len(d):
                    break
                sb = u16(co + 4); vb = u16(co + 6); sp = u32(co + 8); vp = u32(co + 0x10)
                nv = vb // 16
                counts = _strips(d, sp, sb, nv)
                base = len(V)
                for i in range(nv):
                    o = vp + i * 16
                    if o + 16 > len(d):
                        break
                    uu, vv = struct.unpack_from("<2h", d, o)
                    px, py, pz = struct.unpack_from("<3h", d, o + 0x0A)
                    V.append((px / quant * scale, py / quant * scale, pz / quant * scale))
                    UV.append((uu / uv_div, vv / uv_div))
                vi = base
                for cnt in counts:
                    for j in range(cnt - 2):
                        a, b, c = vi + j, vi + j + 1, vi + j + 2
                        if j % 2:
                            a, b = b, a
                        T.append((a, b, c))
                    vi += cnt
                co += 0x28
        Va = np.array(V) if V else np.zeros((0, 3))
        kept = [t for t in T if max(t) < len(Va) and np.linalg.norm(
            np.cross(Va[t[1]] - Va[t[0]], Va[t[2]] - Va[t[0]])) > 1e-6]
        allV.append(Va); allUV.append(np.array(UV) if UV else np.zeros((0, 2)))
        allT.append(kept)
        allM.append(manifest.get(hashes[si], {}).get("name") if si < len(hashes) else None)
    return allV, allUV, allT, allM


def terrain_prims(d: bytes, manifest: Dict[str, dict], uv_div: float):
    """decode_terrain -> the (verts, uvs, tris, tex, is_tie=False) prim tuples that
    sm_glb.write_glb consumes (dropping empty submeshes)."""
    tv, tuv, tt, tmats = decode_terrain(d, manifest, uv_div)
    return [(tv[si], tuv[si], tt[si], tmats[si], False)
            for si in range(len(tv)) if tt[si]]


def main() -> None:
    import sm_glb
    ap = argparse.ArgumentParser(description="Export a terrain GDE to a textured GLB.")
    ap.add_argument("terrain", type=Path, help="terrain STATIC .gde")
    ap.add_argument("--png", type=Path, required=True, help="dir from gim_to_png --wad (manifest.json)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--terrain-uv-div", type=float, default=4096.0,
                    help="terrain UV divisor (4096 default; 2048 tiles seamlessly across chunks)")
    args = ap.parse_args()
    manifest = {e["hash"]: e for e in json.loads((args.png / "manifest.json").read_text())}
    prims = terrain_prims(args.terrain.read_bytes(), manifest, args.terrain_uv_div)
    sm_glb.write_glb(prims, args.png, args.out)


if __name__ == "__main__":
    main()
