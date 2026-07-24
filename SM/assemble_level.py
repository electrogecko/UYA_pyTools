#!/usr/bin/env python3
"""
assemble_level.py - Assemble a textured level (terrain + all placed, textured
TIE instances) into one self-contained binary glTF.

This is a thin orchestrator over the pipeline modules (each independently runnable):
  sm_terrain.py    STATIC/terrain GDE  -> textured prims (native coords, UV divisor)
  sm_placements.py BOG asset           -> [(gde_hash, matrix)] + hash->GDE map
  sm_tie.py        in-level TIE GDE     -> per-material geometry (LOD0)
  sm_glb.py        prims               -> GLB (one object/material, merge/exclude/MASK)

Verified in this branch (see each module's docstring):

TERRAIN  world = pos_s16/4096 * 14.7687  (anchor/radius = cull sphere)
TIE geom world-local = pos_s16/32768 * GDE_scale * (14.7687/4096)   then . matrix
  * SIMPLE meshes  -> instance array BOG+0xB0; +0x04 = GDE hash, matrix = pool[i].
  * COMPLEX meshes -> class table BOG+0x206A0: +0x04 GDE hash, +0x10 -> members.
TIE textures: GDE mesh table hashes; LOD0 display list split by GE opcode 0x1D.
hash -> GDE blob: each ".mb.psp.gde" path is followed by its 0x00010011 blob @+0xBC.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import sm_glb
import sm_placements
import sm_terrain
import sm_tie

# tie model-units -> world.  world = pos/32768 * GDE_scale * WORLD, then .matrix.
# Pinned by a hard geometric constraint: treetrunk01 and treecanopy are placed by
# separate matrices but MUST mesh (branches inside the canopy). Solving "trunk top
# == canopy center" over all 14 trees gives F=0.00971 with std 0.00002 -- identical
# for every tree, so this is the game's true tie scale.
WORLD = 0.0097
# Terrain UV divisor (raw s16 -> UV). /2048 tiles seamlessly across chunk
# boundaries for most terrain textures (rock01 etc.: 0 seams); /4096 leaves a
# half-tile offset at chunk seams.
TERR_UV_DIV = 4096.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bin", type=Path, help="decompressed level WAD payload")
    ap.add_argument("--terrain", type=Path, required=True, help="terrain STATIC .gde")
    ap.add_argument("--png", type=Path, required=True, help="dir from gim_to_png --wad (manifest.json)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--bog", type=lambda x: int(x, 0), default=0xfe0c0)
    ap.add_argument("--tie-scale", type=float, default=WORLD,
                    help="global F: tie world = pos/32768*GDE_scale*F, then .matrix")
    ap.add_argument("--merge-tie-materials", action="store_true",
                    help="TIE prims sharing a texture PNG share one material (select-all in DCC)")
    ap.add_argument("--exclude-list", type=Path, default=None,
                    help="file of Blender-style material names to drop from the export (one per line)")
    ap.add_argument("--terrain-uv-div", type=float, default=TERR_UV_DIV,
                    help="terrain UV divisor (4096 default; 2048 tiles seamlessly across chunks)")
    args = ap.parse_args()

    d = args.bin.read_bytes()
    manifest = {e["hash"]: e for e in json.loads((args.png / "manifest.json").read_text())}

    # ---- gather placements: (gde_hash, 4x4 matrix) ----
    hash2gde = sm_placements.hash_to_gde(d)
    placements = sm_placements.read_placements(d, args.bog, hash2gde)
    print(f"{len(placements)} tie placements ({len(hash2gde)} in-level GDEs)")

    tie_cache = {}
    def get_tie(h):
        if h not in tie_cache:
            tie_cache[h] = sm_tie.decode_tie(d, hash2gde[h], manifest, args.tie_scale) \
                if h in hash2gde else None
        return tie_cache[h]

    # ---- build GLB primitives ----
    prims = []      # (world_verts Nx3, uvs Nx2, tris list, tex_name or None, is_tie)
    # terrain
    prims.extend(sm_terrain.terrain_prims(args.terrain.read_bytes(), manifest, args.terrain_uv_div))
    # ties (bake transforms)
    for h, M in placements:
        t = get_tie(h)
        if t is None:
            continue
        V, UV, tris, mats = t
        hom = np.hstack([V, np.ones((len(V), 1))])
        W = (hom @ M)[:, :3]
        for mi, tl in tris.items():
            if tl:
                prims.append((W, UV, tl, mats[mi] if mi < len(mats) else None, True))

    exclude = set()
    if args.exclude_list:
        for line in args.exclude_list.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                exclude.add(line)
    sm_glb.write_glb(prims, args.png, args.out,
                     merge_ties=args.merge_tie_materials, exclude=exclude)


if __name__ == "__main__":
    main()
