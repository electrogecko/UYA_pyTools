#!/usr/bin/env python3
"""
sm_glb.py - Write level primitives to a self-contained binary glTF, one
mesh/node per material (each imports as its own object in a DCC). Supports
merging TIE materials that share a texture, and excluding materials by their
Blender-style name. (Extracted verbatim from assemble_level.py; output unchanged.)

A prim is (verts Nx3, uvs Nx2, tris [(a,b,c)], tex_name_or_None, is_tie).
"""

from __future__ import annotations

import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import numpy as np

_alpha_cache: Dict[str, bool] = {}


def _png_has_alpha(path) -> bool:
    """True if the PNG has any transparent texels (-> alpha-clip MASK material)."""
    p = str(path)
    if p not in _alpha_cache:
        from PIL import Image
        im = Image.open(path)
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            a = np.asarray(im.convert("RGBA"))[:, :, 3]
            _alpha_cache[p] = bool((a < 255).any())
        else:
            _alpha_cache[p] = False
    return _alpha_cache[p]


def _blender_names(mat_list: List[Optional[str]]) -> List[str]:
    """Replicate how Blender's glTF importer names materials: the glTF name, with
    '.001'/'.002' for repeats, and 'Material_<index>' for unnamed (flat) ones."""
    seen: Dict[str, int] = {}; names: List[str] = []
    for idx, nm in enumerate(mat_list):
        if nm is None:
            names.append(f"Material_{idx}")
        else:
            c = seen.get(nm, 0); seen[nm] = c + 1
            names.append(nm if c == 0 else f"{nm}.{c:03d}")
    return names


def write_glb(prims, png_dir, out, merge_ties: bool = False, exclude: Optional[Set[str]] = None) -> None:
    """Emit a GLB with ONE mesh/node per material (each imports as its own object).
    `exclude` is a set of Blender-style material names to drop from the export."""
    exclude = exclude or set()

    # --- 1. assign each prim a material id, in creation order (so the derived
    #        Blender names line up with what an import of the full model shows) ---
    mat_names: List[Optional[str]] = []   # material id -> texture name or None (flat)
    tie_cache: Dict[str, int] = {}
    prim_mat: List[int] = []
    for V, UV, tris, tex, is_tie in prims:
        if tex is None:
            mid = len(mat_names); mat_names.append(None)
        elif merge_ties and is_tie and tex in tie_cache:
            mid = tie_cache[tex]
        else:
            mid = len(mat_names); mat_names.append(tex)
            if merge_ties and is_tie:
                tie_cache[tex] = mid
        prim_mat.append(mid)
    bnames = _blender_names(mat_names)
    excluded = {i for i, bn in enumerate(bnames) if bn in exclude}
    if exclude:
        hit = {bn for i, bn in enumerate(bnames) if i in excluded}
        for miss in sorted(exclude - hit):
            print(f"  exclude: '{miss}' matched no material")
        print(f"  excluded {len(excluded)} materials: {sorted(hit)}")

    # --- 2. GLB resources (only for kept materials) ---
    bin_data = bytearray(); bvs = []; accs = []
    images = []; textures = []; materials = []; pcache: Dict[str, int] = {}

    def view(blob, target=None):
        while len(bin_data) % 4:
            bin_data.append(0)
        off = len(bin_data); bin_data.extend(blob)
        bv = {"buffer": 0, "byteOffset": off, "byteLength": len(blob)}
        if target:
            bv["target"] = target
        bvs.append(bv); return len(bvs) - 1

    remap: Dict[int, int] = {}   # old material id -> new gltf material index
    for old in range(len(mat_names)):
        if old in excluded:
            continue
        nm = mat_names[old]
        if nm is None:
            materials.append({"name": bnames[old],
                              "pbrMetallicRoughness": {"baseColorFactor": [.8, .3, .8, 1]},
                              "doubleSided": True})
        else:
            png = png_dir / f"{nm}.png"
            if nm not in pcache:
                iv = view(png.read_bytes())
                images.append({"bufferView": iv, "mimeType": "image/png"})
                textures.append({"source": len(images) - 1, "sampler": 0})
                pcache[nm] = len(textures) - 1
            mat = {"name": bnames[old], "pbrMetallicRoughness": {
                "baseColorTexture": {"index": pcache[nm]}, "metallicFactor": 0, "roughnessFactor": 1},
                "doubleSided": True}
            if _png_has_alpha(png):   # foliage/fringe cutouts -> alpha-clip
                mat["alphaMode"] = "MASK"; mat["alphaCutoff"] = 0.5
            materials.append(mat)
        remap[old] = len(materials) - 1

    # --- 3. build geometry, grouped one mesh per material ---
    prim_by_mat = defaultdict(list)
    kept_verts = 0
    for i, (V, UV, tris, tex, is_tie) in enumerate(prims):
        mid = prim_mat[i]
        if mid in excluded:
            continue
        idx = {}; verts = []; uvs = []; out_tris = []
        for tri in tris:
            # Per-triangle UV seam unwrap: bring each vertex within one texture period
            # (16.0 = 65536/4096) of the first vertex. Some meshes (asteroid TIE) store
            # UVs as s16 that wrap at +-32768, so a coord that should read -8.02 lands at
            # +7.98 and the triangle smears across ~15 tiles. Whole-period shifts are
            # texel-neutral under wrap=repeat and weld the seam; seam verts get split.
            base = UV[tri[0]]
            tuv = [base]
            for vi in tri[1:]:
                tuv.append(UV[vi] - np.round((UV[vi] - base) / 16.0) * 16.0)
            nt = []
            for k, vi in enumerate(tri):
                key = (vi, round(tuv[k][0] * 256), round(tuv[k][1] * 256))
                if key not in idx:
                    idx[key] = len(verts); verts.append(V[vi]); uvs.append(tuv[k])
                nt.append(idx[key])
            out_tris.append(nt)
        verts = np.array(verts); uvs = np.array(uvs); kept_verts += len(verts)
        pv = view(verts.astype("<f4").tobytes(), 34962)
        accs.append({"bufferView": pv, "componentType": 5126, "count": len(verts),
                     "type": "VEC3", "min": verts.min(0).tolist(), "max": verts.max(0).tolist()})
        uvv = view(uvs.astype("<f4").tobytes(), 34962)
        accs.append({"bufferView": uvv, "componentType": 5126, "count": len(uvs), "type": "VEC2"})
        iv = view(np.array(out_tris, "<u4").tobytes(), 34963)
        accs.append({"bufferView": iv, "componentType": 5125, "count": len(out_tris) * 3, "type": "SCALAR"})
        prim_by_mat[remap[mid]].append({"attributes": {"POSITION": len(accs) - 3, "TEXCOORD_0": len(accs) - 2},
                                        "indices": len(accs) - 1, "material": remap[mid]})

    # --- 4. one mesh + node per material ---
    meshes = []; nodes = []
    for new_mid in sorted(prim_by_mat):
        meshes.append({"name": materials[new_mid]["name"], "primitives": prim_by_mat[new_mid]})
        nodes.append({"name": materials[new_mid]["name"], "mesh": len(meshes) - 1})

    gltf = {"asset": {"version": "2.0", "generator": "assemble_level.py"}, "scene": 0,
            "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
            "materials": materials, "accessors": accs, "bufferViews": bvs,
            "buffers": [{"byteLength": len(bin_data)}]}
    if images:
        gltf["images"] = images; gltf["textures"] = textures
        gltf["samplers"] = [{"wrapS": 10497, "wrapT": 10497, "magFilter": 9729, "minFilter": 9987}]
    js = bytearray(json.dumps(gltf, separators=(",", ":")).encode())
    while len(js) % 4:
        js += b" "
    while len(bin_data) % 4:
        bin_data.append(0)
    total = 12 + 8 + len(js) + 8 + len(bin_data)
    with open(out, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(bin_data), b"BIN\x00")); f.write(bin_data)
    print(f"Wrote {out}: {len(nodes)} objects (one per material), {len(images)} textures, {kept_verts} verts")
