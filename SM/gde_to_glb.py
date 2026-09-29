#!/usr/bin/env python3
"""
gde_to_glb.py - Export GDE render meshes to binary glTF (.glb).

STATIC/terrain: one glTF primitive per submesh. With `--png <dir>` (a directory
produced by `gim_to_png.py --wad`, containing manifest.json) each submesh is
TEXTURED -- its material hash (GDE mesh table @+0x14, 20-byte entries) is looked
up in the manifest and the correct PNG is embedded, with UVs. Without `--png`,
falls back to a distinct flat colour per submesh (geometry sanity check).

Geometry uses the verified NATIVE model from gde_to_obj (world = pos/4096 *
14.7687; anchor/radius are a cull sphere, not a transform). Vertices are kept
per-chunk (unwelded) so each keeps its own UV -- welding by position alone would
merge distinct UVs at seams and smear the texturing.
"""

from __future__ import annotations

import argparse
import io
import json
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import gde_to_obj as G

Vec = Tuple[float, float, float]
UV = Tuple[float, float]

_alpha_cache: Dict[str, bool] = {}


def _png_has_alpha(path) -> bool:
    """True if the PNG has any transparent texels (-> alpha-clip MASK material)."""
    p = str(path)
    if p not in _alpha_cache:
        import numpy as _np
        from PIL import Image
        im = Image.open(path)
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            _alpha_cache[p] = bool((_np.asarray(im.convert("RGBA"))[:, :, 3] < 255).any())
        else:
            _alpha_cache[p] = False
    return _alpha_cache[p]


def decode_static_submeshes(d: bytes) -> List[Tuple[List[Vec], List[UV], List[Tuple[int, int, int]]]]:
    """[(verts, uvs, tris)] per terrain submesh (native coords, local-indexed)."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    u16 = lambda o: struct.unpack_from("<H", d, o)[0]
    arr = u32(0x1C)
    nsub = u32(arr + 0x10)
    subs = [u32(arr + 0x1C + i * 8 + 4) for i in range(nsub)]
    out = []
    for sub_off in subs:
        verts: List[Vec] = []
        uvs: List[UV] = []
        tris: List[Tuple[int, int, int]] = []
        if sub_off:
            nch = u16(sub_off + 2)
            coff = u32(sub_off + 4)
            for _ in range(nch):
                if coff + 0x28 > len(d):
                    break
                strip_bytes = u16(coff + 4)
                vtx_bytes = u16(coff + 6)
                strips_ptr = u32(coff + 8)
                vtx_ptr = u32(coff + 0x10)
                nverts = vtx_bytes // 16
                counts = G.parse_strips(d, strips_ptr, strip_bytes, nverts)
                base = len(verts)
                for i in range(nverts):
                    o = vtx_ptr + i * 16
                    if o + 16 > len(d):
                        break
                    uu, vv = struct.unpack_from("<2h", d, o)
                    px, py, pz = struct.unpack_from("<3h", d, o + 0x0A)
                    verts.append((px / G.STATIC_QUANT * G.STATIC_SCALE,
                                  py / G.STATIC_QUANT * G.STATIC_SCALE,
                                  pz / G.STATIC_QUANT * G.STATIC_SCALE))
                    uvs.append((uu / 4096.0, vv / 4096.0))  # no V-flip (matches the texture orientation)
                tris.extend(G.strip_tris(counts, base))
                coff += 0x28
        n = len(verts)
        kept = [t for t in tris
                if t[0] < n and t[1] < n and t[2] < n
                and G._area2(verts[t[0]], verts[t[1]], verts[t[2]]) > 1e-6]
        out.append((verts, uvs, kept))
    return out


def static_hashes(d: bytes) -> List[str]:
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    mtab = u32(0x14)
    nmesh = u32(0x10)
    return [f"{u32(mtab + i * 20):08x}" for i in range(nmesh)]


def decode_tie_submeshes(d: bytes) -> List[Tuple[List[Vec], List[UV], List[Tuple[int, int, int]]]]:
    # TIE submeshes are LOD levels of one object; export descriptor 0 = LOD0.
    # Descriptor +0x14 is the vertex-block SIZE in bytes (not an end pointer).
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    desc = u32(0x1C)
    v_start = u32(desc + 0x18)
    scale = struct.unpack_from("<f", d, desc + 0x0C)[0]
    meshbatch = u32(desc + 0x24)
    strips_off = u32(meshbatch + 0x08)
    nverts = u32(desc + 0x14) // 16
    counts = G.parse_strips(d, strips_off, nverts * 8 + 4096, nverts)
    verts: List[Vec] = []
    uvs: List[UV] = []
    for i in range(nverts):
        o = v_start + i * 16
        uu, vv = struct.unpack_from("<2h", d, o)
        px, py, pz = struct.unpack_from("<3h", d, o + 0x0A)
        verts.append((px / 32768 * scale, py / 32768 * scale, pz / 32768 * scale))
        uvs.append((uu / 4096.0, vv / 4096.0))
    tris = [t for t in G.strip_tris(counts, 0)
            if max(t) < len(verts) and G._area2(verts[t[0]], verts[t[1]], verts[t[2]]) > 1e-6]
    return [(verts, uvs, tris)]


def _pad(b: bytearray, align: int = 4) -> None:
    while len(b) % align:
        b += b"\x00"


def write_glb(submeshes, out: Path, *, hashes: Optional[List[str]] = None,
              png_dir: Optional[Path] = None) -> None:
    """Write a .glb. If hashes+png_dir (with manifest.json) are given, texture
    each submesh by its hash; else assign a distinct flat colour per submesh."""
    manifest: Dict[str, dict] = {}
    if png_dir is not None:
        for e in json.loads((png_dir / "manifest.json").read_text()):
            manifest[e["hash"]] = e

    bin_data = bytearray()
    bufferViews: List[dict] = []
    accessors: List[dict] = []
    primitives: List[dict] = []
    images: List[dict] = []
    textures: List[dict] = []
    materials: List[dict] = []
    png_cache: Dict[str, int] = {}
    import colorsys
    n = len(submeshes)

    def add_view(blob: bytes, target: Optional[int] = None) -> int:
        _pad(bin_data)
        off = len(bin_data); bin_data.extend(blob)
        bv = {"buffer": 0, "byteOffset": off, "byteLength": len(blob)}
        if target:
            bv["target"] = target
        bufferViews.append(bv)
        return len(bufferViews) - 1

    def textured_material(hsh: str) -> Optional[int]:
        e = manifest.get(hsh)
        if e is None:
            return None
        png = png_dir / f"{e['name']}.png"
        if e["name"] not in png_cache:
            iv = add_view(png.read_bytes())
            images.append({"bufferView": iv, "mimeType": "image/png"})
            textures.append({"source": len(images) - 1, "sampler": 0})
            png_cache[e["name"]] = len(textures) - 1
        mat = {"name": e["name"],
               "pbrMetallicRoughness": {
                   "baseColorTexture": {"index": png_cache[e["name"]]},
                   "metallicFactor": 0.0, "roughnessFactor": 1.0},
               "doubleSided": True}
        if _png_has_alpha(png):   # foliage/fringe cutouts -> alpha-clip
            mat["alphaMode"] = "MASK"; mat["alphaCutoff"] = 0.5
        materials.append(mat)
        return len(materials) - 1

    for si, (verts, uvs, tris) in enumerate(submeshes):
        if not verts or not tris:
            continue
        # Weld UV storage-seam striping (s16 UV wrap) by unwrapping per triangle.
        verts, uvs, tris = G.unwrap_uv_seams(verts, uvs, tris)
        pos = bytearray(); mn = [1e30]*3; mx = [-1e30]*3
        for v in verts:
            pos += struct.pack("<3f", *v)
            for k in range(3):
                mn[k] = min(mn[k], v[k]); mx[k] = max(mx[k], v[k])
        pv = add_view(pos, 34962)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": len(verts),
                          "type": "VEC3", "min": mn, "max": mx})
        pos_acc = len(accessors) - 1

        attrs = {"POSITION": pos_acc}
        mat: Optional[int] = None
        if hashes is not None and si < len(hashes):
            mat = textured_material(hashes[si])
        if mat is not None:
            uvb = bytearray()
            for u, v in uvs:
                uvb += struct.pack("<2f", u, v)
            uvv = add_view(uvb, 34962)
            accessors.append({"bufferView": uvv, "componentType": 5126,
                              "count": len(uvs), "type": "VEC2"})
            attrs["TEXCOORD_0"] = len(accessors) - 1
        else:
            r, g, b = colorsys.hsv_to_rgb((si / max(1, n)) % 1.0, 0.6, 0.9)
            materials.append({"name": f"submesh_{si}",
                              "pbrMetallicRoughness": {"baseColorFactor": [r, g, b, 1.0],
                                                       "metallicFactor": 0.0, "roughnessFactor": 1.0},
                              "doubleSided": True})
            mat = len(materials) - 1

        idx = bytearray()
        for a, b, c in tris:
            idx += struct.pack("<3I", a, b, c)
        iv = add_view(idx, 34963)
        accessors.append({"bufferView": iv, "componentType": 5125, "count": len(tris) * 3, "type": "SCALAR"})
        primitives.append({"attributes": attrs, "indices": len(accessors) - 1, "material": mat})

    gltf = {
        "asset": {"version": "2.0", "generator": "gde_to_glb.py"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": primitives}],
        "materials": materials,
        "accessors": accessors, "bufferViews": bufferViews,
        "buffers": [{"byteLength": len(bin_data)}],
    }
    if images:
        gltf["images"] = images
        gltf["textures"] = textures
        gltf["samplers"] = [{"wrapS": 10497, "wrapT": 10497, "magFilter": 9729, "minFilter": 9987}]

    json_bytes = bytearray(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    while len(json_bytes) % 4:
        json_bytes += b" "
    while len(bin_data) % 4:
        bin_data += b"\x00"

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    with open(out, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(json_bytes), b"JSON")); f.write(json_bytes)
        f.write(struct.pack("<I4s", len(bin_data), b"BIN\x00")); f.write(bin_data)
    print(f"Wrote {out}: {len(primitives)} submeshes, {len(images)} textures, "
          f"{sum(len(v) for v,_,_ in submeshes)} verts, {sum(len(t) for _,_,t in submeshes)} tris")


def main() -> None:
    ap = argparse.ArgumentParser(description="Decode GDE meshes to textured glTF.")
    ap.add_argument("gde", type=Path, help="A STATIC/terrain or TIE *.gde")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--png", type=Path, default=None,
                    help="Directory from `gim_to_png.py --wad` (with manifest.json) to texture submeshes by hash")
    args = ap.parse_args()
    d = args.gde.read_bytes()
    cls = struct.unpack_from("<I", d, 4)[0]
    if cls == G.CLASS_STATIC:
        write_glb(decode_static_submeshes(d), args.out,
                  hashes=static_hashes(d), png_dir=args.png)
    elif cls == G.CLASS_TIE:
        write_glb(decode_tie_submeshes(d), args.out)
    else:
        raise SystemExit(f"Unknown GDE class 0x{cls:08x}")


if __name__ == "__main__":
    main()
