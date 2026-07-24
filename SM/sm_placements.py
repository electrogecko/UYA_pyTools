#!/usr/bin/env python3
"""
sm_placements.py - Resolve a level's TIE placements from its BOG asset, plus the
level-wide hash->GDE map. (Extracted verbatim from assemble_level.py; the
arithmetic is identical, so full-level output is unchanged.)

hash -> GDE blob (struct-locked):
  each "[u32 hash][X:\\...\\name.mb.<tag>.gde]" path in the payload is followed
  by its 0x00010011 GDE blob at exactly +0xBC. No backward scanning.

TIE placement in the BOG (default @0xfe0c0):
  * SIMPLE  -> instance array BOG+0xB0 (stride 52); +0x04 = GDE hash (struct-locked
      to an in-level GDE), matrix = pool[i] at BOG+u32(BOG+0x34) (stride 0x80).
  * COMPLEX -> class table BOG+u32(BOG+0x54), count BOG+0x58 (stride 24):
      +0x04 GDE hash, +0x10 -> member array (stride 100, 4x4 matrix at +0x00),
      +0x14 = member count.
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

MAGIC = 0x00010011
PATH_GDE = re.compile(rb"[A-Za-z]:\\[ -~]{3,120}?\.mb\.[A-Za-z0-9]{3}\.gde")


def hash_to_gde(d: bytes) -> Dict[int, int]:
    """{gde_hash: blob_offset} for every in-level GDE (struct-locked at +0xBC)."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    h2g: Dict[int, int] = {}
    for m in PATH_GDE.finditer(d):
        s = m.start(); blob = s + 0xBC
        if d[blob:blob + 4] == struct.pack("<I", MAGIC):
            h2g[u32(s - 4)] = blob
    return h2g


def read_placements(d: bytes, bog: int, hash2gde: Dict[int, int]) -> List[Tuple[int, np.ndarray]]:
    """[(gde_hash, 4x4 matrix)] from the BOG: simple instance array + complex class table.
    Only simple instances whose hash resolves to an in-level GDE are kept (matching
    assemble_level's original filter); complex entries are emitted unconditionally."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    f32 = lambda o: struct.unpack_from("<f", d, o)[0]
    b = bog
    placements: List[Tuple[int, np.ndarray]] = []
    # SIMPLE: instance array, +0x04 GDE hash resolvable to an in-level blob
    ia = b + 0xB0; pool = b + u32(b + 0x34)
    for i in range(u32(b + 0x28)):
        h = u32(ia + i * 52 + 0x04)
        if h in hash2gde:
            M = np.array([f32(pool + i * 0x80 + k * 4) for k in range(16)]).reshape(4, 4)
            placements.append((h, M))
    # COMPLEX: class table -> per-member matrices
    tbl = b + u32(b + 0x54); ncls = u32(b + 0x58)
    for c in range(ncls):
        e = tbl + c * 24; h = u32(e + 0x04); moff = b + u32(e + 0x10); cnt = u32(e + 0x14)
        for j in range(cnt):
            M = np.array([f32(moff + j * 100 + k * 4) for k in range(16)]).reshape(4, 4)
            placements.append((h, M))
    return placements


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump a level's TIE placement table.")
    ap.add_argument("bin", type=Path, help="decompressed level WAD payload")
    ap.add_argument("--bog", type=lambda x: int(x, 0), default=0xfe0c0)
    args = ap.parse_args()
    d = args.bin.read_bytes()
    h2g = hash_to_gde(d)
    placements = read_placements(d, args.bog, h2g)
    per_hash: Dict[int, int] = {}
    for h, _ in placements:
        per_hash[h] = per_hash.get(h, 0) + 1
    print(f"{len(placements)} placements, {len(h2g)} in-level GDEs, "
          f"{len(per_hash)} distinct placed hashes")
    for h in sorted(per_hash, key=lambda k: -per_hash[k]):
        mark = "" if h in h2g else "  (no in-level GDE)"
        print(f"  {h:08x} x{per_hash[h]}{mark}")


if __name__ == "__main__":
    main()
