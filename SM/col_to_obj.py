#!/usr/bin/env python3
"""
col_to_obj.py - Extract `COL ` collision meshes from a *decompressed* HIG WAD
payload and write them as Wavefront OBJ.

Format (confirmed against the decompilation). A `COL ` block is an **indexed**
mesh:

  +0x00 char[4] "COL "
  +0x04 u32     version (0x08)
  +0x08 u32     vertex count   (A)
  +0x0C u32     polygon count  (B)
  +0x10 u32     grid data size (C)
  +0x14 u32     grid cell count (D = nx*ny*nz)
  +0x18 u32[3]  grid dims (nx,ny,nz)   +0x24 f32[3] cell size
  +0x30 f32[3]  AABB min       +0x3C f32[3] AABB max
  +0x48 ...     (a few header floats; header size varies per block)
  <verts>       A * (3 x f32)            -- flat vertex array
  <polys>       B * 76-byte structs; first 3 u16 = vertex indices, then the
                face normal / bounds / material id
  <grid>        u16 cell -> polygon acceleration structure (not needed here)

NOTE: an earlier version of this tool read the vertex array as a flat triangle
"soup" (9 floats = 1 tri). That was wrong -- it undercounted triangles ~4x, gave
0% shared edges, and produced ~100 "sliver" artifacts (reads crossing the
vert/poly array boundary). The indexed decode below yields a properly connected
surface (70-90%+ shared edges) with no heuristics.

Usage:
  python3 col_to_obj.py decompressed.bin -o outdir/            # all blocks
  python3 col_to_obj.py decompressed.bin -o outdir/ --combined # + merged.obj
"""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path
from typing import List, Tuple, Optional

COL_SIG = b"COL "
Vec = Tuple[float, float, float]


def _u32(d: bytes, o: int) -> int:
    return struct.unpack_from("<I", d, o)[0]


def decode_col_block(blob: bytes, base: int
                     ) -> Optional[Tuple[List[Vec], List[Tuple[int, int, int]]]]:
    """Return (vertices, triangles) for the indexed COL block at `base`."""
    vcount = _u32(blob, base + 0x08)
    pcount = _u32(blob, base + 0x0C)
    if vcount == 0 or pcount == 0 or vcount > 1 << 20 or pcount > 1 << 20:
        return None
    # Fixed 88-byte (0x58) header, then the two arrays back-to-back:
    #   verts   at 0x58            (vcount * 12 bytes)
    #   polys   at 0x58 + vcount*12 (pcount * 76 bytes)
    # Confirmed structurally: for every block pstart - vcount*12 == 0x58 exactly.
    # (Earlier scan-based detection could land on header floats and misalign the
    # whole vertex array, producing spurious long faces.)
    HEADER = 0x58
    POLY_STRIDE = 76
    if base + HEADER + vcount * 12 + pcount * POLY_STRIDE > len(blob):
        return None
    vbase = base + HEADER
    verts = [struct.unpack_from("<3f", blob, vbase + i * 12) for i in range(vcount)]
    pbase = vbase + vcount * 12
    tris = []
    for k in range(pcount):
        a, b, c = struct.unpack_from("<3H", blob, pbase + k * POLY_STRIDE)
        if a < vcount and b < vcount and c < vcount:
            tris.append((a, b, c))
    return verts, tris


def find_col_blocks(blob: bytes) -> List[int]:
    offs, s = [], 0
    while True:
        i = blob.find(COL_SIG, s)
        if i == -1:
            break
        offs.append(i)
        s = i + 4
    return offs


def collect_col_names(blob: bytes) -> List[str]:
    """All `<name>.mb.col` basenames, in file order (for best-effort naming)."""
    names, s = [], 0
    needle = b".mb.col"
    while True:
        i = blob.find(needle, s)
        if i == -1:
            break
        a = i
        while a > 0 and 32 <= blob[a - 1] < 127 and i - a < 200:
            a -= 1
        path = blob[a:i].decode("latin1", "replace")
        names.append(path.replace("\\", "/").split("/")[-1])
        s = i + 1
    return names


def _area(a: Vec, b: Vec, c: Vec) -> float:
    u = (b[0]-a[0], b[1]-a[1], b[2]-a[2]); v = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
    cx, cy, cz = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    return 0.5 * math.sqrt(cx*cx + cy*cy + cz*cz)


def write_obj(path: Path, verts: List[Vec], tris: List[Tuple[int, int, int]], header: str) -> int:
    kept = [t for t in tris if _area(verts[t[0]], verts[t[1]], verts[t[2]]) > 1e-5]
    with open(path, "w") as o:
        o.write(f"# {header}\n")
        for x, y, z in verts:
            o.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
        for a, b, c in kept:
            o.write(f"f {a+1} {b+1} {c+1}\n")
    return len(kept)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("blob", type=Path, help="Decompressed WAD payload (from wad_extract.py decompress)")
    ap.add_argument("-o", "--out", type=Path, required=True, help="Output directory")
    ap.add_argument("--combined", action="store_true", help="Also write a merged all.obj")
    ap.add_argument("--min-tris", type=int, default=1, help="Skip blocks with fewer triangles")
    args = ap.parse_args()

    blob = args.blob.read_bytes()
    args.out.mkdir(parents=True, exist_ok=True)

    blocks = find_col_blocks(blob)
    names = collect_col_names(blob)
    name_by_index: Optional[List[str]] = names if len(names) == len(blocks) else None

    combined_v: List[Vec] = []
    combined_t: List[Tuple[int, int, int]] = []
    total = 0
    for i, base in enumerate(blocks):
        res = decode_col_block(blob, base)
        if not res or len(res[1]) < args.min_tris:
            print(f"  skip COL @0x{base:x} ({'no polys' if not res or not res[1] else str(len(res[1]))+' tris'})")
            continue
        verts, tris = res
        stem = (name_by_index[i].replace(".mb.col", "") if name_by_index else f"col_{base:08x}")
        stem = "".join(c if c.isalnum() or c in "_-." else "_" for c in stem) or f"col_{base:08x}"
        out_path = args.out / f"{stem}.obj"
        if out_path.exists():
            out_path = args.out / f"{stem}_{base:08x}.obj"
        nf = write_obj(out_path, verts, tris, f"COL @0x{base:x} verts={len(verts)} tris={len(tris)}")
        base_i = len(combined_v)
        combined_v.extend(verts)
        combined_t.extend((a + base_i, b + base_i, c + base_i) for a, b, c in tris)
        total += nf
        print(f"  {out_path.name:32s} {len(verts):5d} v  {nf:5d} tris  (COL @0x{base:x})")

    if args.combined and combined_t:
        write_obj(args.out / "all.obj", combined_v, combined_t, "All COL blocks merged")
        print(f"  all.obj                          {len(combined_v):5d} v  {len(combined_t):5d} tris")

    print(f"Done. {len(blocks)} COL blocks, {total} triangles -> {args.out}"
          + ("" if name_by_index else "  (names by offset; .mb.col count != block count)"))


if __name__ == "__main__":
    main()
