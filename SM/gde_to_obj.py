#!/usr/bin/env python3
"""
gde_to_obj.py - Decode High Impact "GDE" render meshes to Wavefront OBJ with UVs.

Both mesh classes are solved. Terrain-chunk decoding + the "PRIM command"
insight are from the decomp agent; the tie vertex struct (position offset) is
corrected here.

Header (LE):
  +0x00 u32  magic 0x00010011
  +0x04 u32  class: 0x10000000 = STATIC/terrain (chunked), 0x10000004 = TIE/object
  +0x10 u32  mesh count      +0x14 u32 -> mesh table
  +0x1C u32  -> descriptor / submesh-array table

Geometry primitives are triangle strips. The strip list is a run of GE
PRIM commands: opcode (top byte) 0x04, vertex count = (cmd & 0xFFFF), prim type
= (cmd>>16)&7 (== 4, TRIANGLE_STRIP). 0xffeeddcc/0xccddeeff words are padding.

16-byte vertex structs (position is 3x s16, dequantized):
  TIE   (0x10000004): UV(2xs16) Normal(3xs16) Pos(3xs16 @ +0x0A)
                      world = pos/32768 * scale     (scale = descriptor +0x0C)
  STATIC(0x10000000): UV(2xs16) Color(u16 5551) Normal(3xs8) Pos(3xs16 @ +0x0A)
                      world = pos/4096 * 14.7687    (NATIVE absolute coords)
UVs are s16/4096.

STATIC coordinate model (VERIFIED, session 89fb3dfe):
  Terrain vertices are ALREADY absolute world coordinates -- s16 fixed-point 4.12
  (/4096) at a global model scale of 14.7687. The per-chunk `anchor`(3f @+0x18)
  and `radius`(f @+0x24) are a FRUSTUM-CULLING BOUNDING SPHERE computed from those
  verts (anchor == centroid, radius == bounding radius), NOT a placement transform.
  The earlier `anchor + pos/32768*radius` formula double-transformed -- it added the
  cull-sphere center (scattering chunks) and scaled ~9x too small -- which is why the
  terrain looked like disconnected islands. Native /4096*14.7687 assembles it gap-free.
  Scale 14.7687 was recovered from the anchors with zero variance (anchor==centroid*K);
  the authoritative literal lives in the EBOOT.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import List, Tuple

Vec = Tuple[float, float, float]
GDE_MAGIC = 0x00010011
CLASS_TIE = 0x10000004
CLASS_STATIC = 0x10000000
PAD_WORDS = (0xFFEEDDCC, 0xCCDDEEFF, 0x00000000)
# STATIC terrain dequant: world = pos_s16 / STATIC_QUANT * STATIC_SCALE
STATIC_QUANT = 4096.0
STATIC_SCALE = 14.7687


def _u32(d, o): return struct.unpack_from("<I", d, o)[0]
def _u16(d, o): return struct.unpack_from("<H", d, o)[0]
def _f32(d, o): return struct.unpack_from("<f", d, o)[0]


def parse_strips(d: bytes, off: int, nbytes: int, vert_budget: int) -> List[int]:
    """GE display-list walk within [off, off+nbytes): collect PRIM (opcode 0x04)
    triangle-strip vertex counts, SKIP interleaved state/padding commands, and
    stop at the vertex budget.

    TIE strip lists interleave GE state commands (e.g. 0x1d…) between the strip
    PRIMs; an earlier version broke at the first non-PRIM word and truncated those
    meshes (saucer/tank/cowSign lost most of their tris). Skipping non-PRIM words
    instead recovers them. Terrain strips are pure-PRIM runs bounded by `nbytes`
    (strip_bytes), so skip-vs-break is identical there (verified byte-for-byte)."""
    counts: List[int] = []
    i, end = off, off + max(nbytes, 4)
    total = 0
    while i + 4 <= min(end, len(d)):
        cmd = _u32(d, i); i += 4
        if (cmd >> 24) & 0xFF == 0x04:          # GE PRIM (triangle strip)
            cnt = cmd & 0xFFFF
            if cnt:
                counts.append(cnt)
                total += cnt
                if total >= vert_budget:
                    break
        # padding (PAD_WORDS) and state commands: skip, keep walking the list
    return counts


def _area2(a: Vec, b: Vec, c: Vec) -> float:
    u = (b[0]-a[0], b[1]-a[1], b[2]-a[2]); v = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
    cx, cy, cz = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    return cx*cx + cy*cy + cz*cz


def unwrap_uv_seams(verts, uvs, tris, period: float = 16.0):
    """Fix s16 UV-wrap striping. Some meshes (e.g. the asteroid TIE) store UVs as
    s16 that wrap at +-32768; a coord that should read -8.02 lands at +7.98, so a
    triangle straddling the seam interpolates across ~15 texture tiles and smears.
    Per triangle, shift each vertex's UV within one period (16.0 == 65536/4096) of
    the first vertex -- texel-neutral under wrap=repeat -- splitting seam vertices.
    Returns (new_verts, new_uvs, new_tris)."""
    nv: list = []
    nu: list = []
    nt: List[Tuple[int, int, int]] = []
    idx: dict = {}
    for tri in tris:
        b = uvs[tri[0]]
        tuv = [b]
        for vi in tri[1:]:
            uv = uvs[vi]
            tuv.append((uv[0] - round((uv[0]-b[0])/period)*period,
                        uv[1] - round((uv[1]-b[1])/period)*period))
        out = []
        for k, vi in enumerate(tri):
            key = (vi, round(tuv[k][0]*256), round(tuv[k][1]*256))
            j = idx.get(key)
            if j is None:
                j = len(nv); idx[key] = j; nv.append(verts[vi]); nu.append(tuv[k])
            out.append(j)
        nt.append((out[0], out[1], out[2]))
    return nv, nu, nt


def strip_tris(counts: List[int], base: int) -> List[Tuple[int, int, int]]:
    """Triangle-strip vertex counts -> 0-based (a,b,c) index triples (rel to base)."""
    tris = []
    vi = base
    for cnt in counts:
        for j in range(cnt - 2):
            a, b, c = vi + j, vi + j + 1, vi + j + 2
            if j % 2:
                a, b = b, a
            tris.append((a, b, c))
        vi += cnt
    return tris


def _write_obj(out: Path, kind: str, verts: List[Vec], uvs: List[Tuple[float, float]],
               tris: List[Tuple[int, int, int]], *,
               weld: Optional[float] = None, max_edge: Optional[float] = None) -> None:
    n = len(verts)

    # Optionally weld near-coincident vertices (grid snap at tolerance `weld`).
    # The GDE stores each triangle strip with its own vertex copies, and each
    # chunk quantizes relative to its own anchor/radius, so abutting patches land
    # at *near*-equal (not equal) positions -- unwelded they read as thousands of
    # separate islands ("fragments"). A tolerance weld merges them.
    if weld:
        inv = 1.0 / weld
        key2new: dict = {}
        new_verts: List[Vec] = []
        new_uvs: List[Tuple[float, float]] = []
        remap = [0] * n
        for i, v in enumerate(verts):
            k = (round(v[0]*inv), round(v[1]*inv), round(v[2]*inv))
            j = key2new.get(k)
            if j is None:
                j = len(new_verts)
                key2new[k] = j
                new_verts.append(v)
                new_uvs.append(uvs[i])
            remap[i] = j
        verts, uvs = new_verts, new_uvs
        tris = [(remap[a], remap[b], remap[c]) for a, b, c in tris if a < n and b < n and c < n]
        n = len(verts)

    def longest_edge(t):
        a, b, c = verts[t[0]], verts[t[1]], verts[t[2]]
        return max(math.dist(a, b), math.dist(b, c), math.dist(c, a))

    # Drop degenerate (zero-area strip-stitch) triangles, dedupe, and optionally
    # drop "giant" strip-boundary artifact triangles (edge > max_edge).
    seen = set()
    kept = []
    dropped_deg = dropped_big = 0
    for t in tris:
        if not (t[0] < n and t[1] < n and t[2] < n):
            continue
        if _area2(verts[t[0]], verts[t[1]], verts[t[2]]) <= 1e-6:
            dropped_deg += 1
            continue
        if max_edge is not None and longest_edge(t) > max_edge:
            dropped_big += 1
            continue
        key = tuple(sorted(t))
        if key in seen:
            continue
        seen.add(key)
        kept.append(t)

    with open(out, "w") as f:
        f.write(f"# {kind} mesh, {len(verts)} verts, {len(kept)} faces "
                f"(dropped {dropped_deg} degenerate"
                + (f", {dropped_big} oversized" if max_edge is not None else "")
                + (", welded" if weld else "") + ")\n")
        for (x, y, z), (u, v) in zip(verts, uvs):
            f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
            f.write(f"vt {u:.4f} {v:.4f}\n")
        for a, b, c in kept:
            f.write(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n")
    _report(out, kind)


def export_tie(d: bytes, out: Path) -> None:
    # TIE header: +0x08 = number of LOD submeshes, +0x1C -> descriptor array
    # (stride 0x30). The "submeshes" are LOD levels of the SAME object (verified:
    # truck 3 LODs / techy 2 LODs -- identical bbox, decreasing vert counts), NOT
    # separate parts -- so we export descriptor 0 = LOD0 (highest detail).
    # Descriptor: +0x0C scale(f32), +0x14 vertex-block SIZE in bytes, +0x18 vertex
    # offset, +0x24 meshbatch. (+0x14 is a byte SIZE, not an end pointer -- the old
    # `(end-start)/16` undercounted every tie's vertices.)
    desc = _u32(d, 0x1C)
    vbytes = _u32(d, desc + 0x14)
    v_start = _u32(d, desc + 0x18)
    scale = _f32(d, desc + 0x0C)
    meshbatch = _u32(d, desc + 0x24)
    strips_off = _u32(d, meshbatch + 0x08)
    nverts = vbytes // 16
    # generous byte cap (strip list is padded with interleaved state cmds); the
    # vertex budget is what actually terminates the walk.
    counts = parse_strips(d, strips_off, nverts * 8 + 4096, nverts)

    verts: List[Vec] = []
    uvs: List[Tuple[float, float]] = []
    for i in range(nverts):
        o = v_start + i * 16
        uu, vv = struct.unpack_from("<2h", d, o)             # UV @ +0
        px, py, pz = struct.unpack_from("<3h", d, o + 0x0A)  # Pos @ +0x0A (after UV+Normal)
        verts.append((px/32768*scale, py/32768*scale, pz/32768*scale))
        uvs.append((uu/4096, vv/4096))
    verts, uvs, tris = unwrap_uv_seams(verts, uvs, strip_tris(counts, 0))
    _write_obj(out, "TIE", verts, uvs, tris)


def export_static(d: bytes, out: Path) -> None:
    arr = _u32(d, 0x1C)
    # Submesh count is at arr+0x10 (== header mesh count at +0x10), NOT arr+0x00
    # (which is 4 -- a type/flags word). Reading arr+0x00 decoded only the first
    # few submeshes, leaving the terrain looking like scattered patches.
    nsub = _u32(d, arr + 0x10)
    subs = [_u32(d, arr + 0x1C + i * 8 + 4) for i in range(nsub)]

    verts: List[Vec] = []
    uvs: List[Tuple[float, float]] = []
    tris: List[Tuple[int, int, int]] = []
    for sub_off in subs:
        nchunks = _u16(d, sub_off + 2)
        coff = _u32(d, sub_off + 4)
        for _ in range(nchunks):
            if coff + 0x28 > len(d):
                break
            strip_bytes = _u16(d, coff + 4)
            vtx_bytes = _u16(d, coff + 6)
            strips_ptr = _u32(d, coff + 8)
            vtx_ptr = _u32(d, coff + 0x10)
            # anchor (3f @+0x18) + radius (f @+0x24) are a cull sphere, NOT a
            # transform -- deliberately unused (see module docstring).
            nverts = vtx_bytes // 16
            counts = parse_strips(d, strips_ptr, strip_bytes, nverts)
            base = len(verts)
            for i in range(nverts):
                o = vtx_ptr + i * 16
                if o + 16 > len(d):
                    break
                # STATIC vertex = GE VTYPE 0x136 (16 bytes):
                #   +0x00 UV       2x s16 (GU_TEXTURE_16BIT), /4096
                #   +0x04 Color    1x u16 (GU_COLOR_5551)
                #   +0x06 Normal   3x s8 + 1 pad (GU_NORMAL_8BIT)
                #   +0x0A Position 3x s16 (GU_VERTEX_16BIT)
                # world = pos/4096 * 14.7687 (absolute; no anchor add, no matrix).
                uu, vv = struct.unpack_from("<2h", d, o)
                px, py, pz = struct.unpack_from("<3h", d, o + 0x0A)
                verts.append((px/STATIC_QUANT*STATIC_SCALE,
                              py/STATIC_QUANT*STATIC_SCALE,
                              pz/STATIC_QUANT*STATIC_SCALE))
                uvs.append((uu/4096, vv/4096))
            tris.extend(strip_tris(counts, base))
            coff += 0x28
    # Weld exact-duplicate seam vertices (adjacent chunks store the shared seam
    # vertex identically -- verified max 0.0019u apart, i.e. float noise). This is
    # duplicate-merging, not gap-closing. Keep all faces -- terrain is
    # mixed-resolution, so a size-filter would delete the large ground faces.
    _write_obj(out, "STATIC", verts, uvs, tris, weld=0.02, max_edge=None)
    _report(out, "STATIC")


def _report(out: Path, kind: str) -> None:
    xs = []; ys = []; zs = []; nf = 0
    for line in open(out):
        if line[:2] == "v ":
            _, x, y, z = line.split(); xs.append(float(x)); ys.append(float(y)); zs.append(float(z))
        elif line[:2] == "f ":
            nf += 1
    if xs:
        print(f"{kind}: {len(xs)} verts, {nf} faces, "
              f"bbox X[{min(xs):.1f},{max(xs):.1f}] Y[{min(ys):.1f},{max(ys):.1f}] Z[{min(zs):.1f},{max(zs):.1f}]")
    print(f"Wrote {out}")


def convert(path: Path, out: Path) -> None:
    d = path.read_bytes()
    if _u32(d, 0) != GDE_MAGIC:
        raise SystemExit(f"Not a GDE file (magic=0x{_u32(d,0):08x})")
    _dispatch(d, _u32(d, 4), out)


def _dispatch(d: bytes, cls: int, out: Path) -> None:
    if cls == CLASS_TIE:
        export_tie(d, out)
    elif cls == CLASS_STATIC:
        export_static(d, out)
    else:
        raise SystemExit(f"Unknown GDE class 0x{cls:08x}")


def _name_near(blob: bytes, off: int) -> str:
    j = blob.rfind(b".mb.psp.gde", max(0, off - 0x4000), off)
    if j < 0:
        j = blob.find(b".mb.psp.gde", off, off + 0x4000)
    if j < 0:
        return f"gde_{off:06x}"
    a = j
    while a > 0 and 32 <= blob[a - 1] < 127 and j - a < 120:
        a -= 1
    nm = blob[a:j].decode("latin1", "replace").replace("\\", "/").split("/")[-1]
    return "".join(c if c.isalnum() or c in "_-." else "_" for c in nm) or f"gde_{off:06x}"


def batch_wad(blob_path: Path, outdir: Path) -> None:
    """Scan a DECOMPRESSED WAD payload for embedded GDE blobs and dump them all."""
    blob = blob_path.read_bytes()
    outdir.mkdir(parents=True, exist_ok=True)
    magic = struct.pack("<I", GDE_MAGIC)
    starts, s = [], 0
    while True:
        i = blob.find(magic, s)
        if i < 0:
            break
        if _u32(blob, i + 4) in (CLASS_STATIC, CLASS_TIE, 0x10000001, 0x10000002):
            starts.append((i, _u32(blob, i + 4)))
        s = i + 4
    offs = [o for o, _ in starts]
    ok = fail = 0
    for idx, (off, cls) in enumerate(starts):
        if cls not in (CLASS_TIE, CLASS_STATIC):
            continue
        end = offs[idx + 1] if idx + 1 < len(offs) else len(blob)
        nm = _name_near(blob, off)
        try:
            _dispatch(blob[off:end], cls, outdir / f"{nm}.obj")
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  FAIL {nm} @0x{off:x}: {type(e).__name__}: {e}")
    print(f"Done. {ok} meshes decoded, {fail} failed -> {outdir}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Decode GDE meshes to OBJ.")
    ap.add_argument("gde", type=Path, help="A single *.mb.gde, or (with --wad) a decompressed WAD payload")
    ap.add_argument("-o", "--out", type=Path, required=True, help="Output OBJ file, or output dir with --wad")
    ap.add_argument("--wad", action="store_true", help="Treat input as a decompressed WAD; dump all embedded GDE meshes")
    args = ap.parse_args()
    if args.wad:
        batch_wad(args.gde, args.out)
    else:
        convert(args.gde, args.out)


if __name__ == "__main__":
    main()
