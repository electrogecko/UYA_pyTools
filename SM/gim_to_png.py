#!/usr/bin/env python3
"""
gim_to_png.py - Decode High Impact GIM-family textures to PNG.

GIM is a block-structured texture container:
  file: signature + 0x10 bytes, then a tree of 16-byte block headers:
    +0x00 u16 id  (2=root, 3=picture, 4=IMAGE, 5=PALETTE, 0xFF=eof)
    +0x02 u16 pad
    +0x04 u32 blockSize        +0x08 u32 nextRel   +0x0C u32 dataRel
  IMAGE / PALETTE data header (at block+dataRel):
    +0x00 u16 headerSize (0x30) +0x04 u16 format  +0x06 u16 pixelOrder(0=linear,1=swizzled)
    +0x08 u16 width             +0x0A u16 height   +0x0C u16 bpp
    +0x1C u32 dataOffset (to pixel/clut data, from this header)
  format: 0=RGBA5650 1=RGBA5551 2=RGBA4444 3=RGBA8888 4=index4 5=index8

Verified on Moon.gim (256x256 index4 + 16-colour RGBA5650 CLUT -> a starfield).

Usage:
  python3 gim_to_png.py texture.gim -o texture.png
  python3 gim_to_png.py indir/ -o outdir/        # batch a directory of .gim
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image


def _blocks(d: bytes):
    """Yield (id, abs_offset, data_abs_offset) for each top-level GIM block."""
    o = 0x10
    while o + 16 <= len(d):
        bid, _, size, nxt, dat = struct.unpack_from("<HHIII", d, o)
        if bid == 0 or bid == 0xFFFF:
            break
        yield bid, o, o + dat
        if nxt == 0:
            break
        o += nxt


def _decode_direct(fmt: int, u16_or_u32: np.ndarray) -> np.ndarray:
    """Decode direct-colour pixels/CLUT entries to Nx4 uint8 RGBA."""
    v = u16_or_u32.astype(np.uint32)
    if fmt == 0:      # RGBA5650 (no alpha)
        r = (v & 0x1F) << 3; g = ((v >> 5) & 0x3F) << 2; b = ((v >> 11) & 0x1F) << 3
        a = np.full_like(r, 255)
    elif fmt == 1:    # RGBA5551
        r = (v & 0x1F) << 3; g = ((v >> 5) & 0x1F) << 3; b = ((v >> 10) & 0x1F) << 3
        a = np.where((v >> 15) & 1, 255, 0)
    elif fmt == 2:    # RGBA4444
        r = (v & 0xF) << 4; g = ((v >> 4) & 0xF) << 4; b = ((v >> 8) & 0xF) << 4
        a = ((v >> 12) & 0xF) << 4
    elif fmt == 3:    # RGBA8888
        r = v & 0xFF; g = (v >> 8) & 0xFF; b = (v >> 16) & 0xFF
        a = np.clip(((v >> 24) & 0xFF) * 255 // 128, 0, 255)  # alpha 0..128
    else:
        raise ValueError(f"not a direct colour format: {fmt}")
    return np.stack([r, g, b, a], axis=-1).astype(np.uint8)


def _unswizzle(raw: bytes, width_bytes: int, height: int) -> bytes:
    """Undo texture swizzle (16-byte x 8-row blocks)."""
    out = bytearray(len(raw))
    bw = 16
    blocks_x = width_bytes // bw
    src = 0
    for by in range(0, height, 8):
        for bx in range(blocks_x):
            for row in range(8):
                dst = (by + row) * width_bytes + bx * bw
                out[dst:dst + bw] = raw[src:src + bw]
                src += bw
    return bytes(out)


MIG_SIG = bytes.fromhex("4D 49 47 2E 30 30 2E 31 50 53 50")


def decode_gim(d: bytes) -> Optional[Image.Image]:
    if d[:len(MIG_SIG)] != MIG_SIG:
        raise ValueError("not a GIM texture")
    image = palette = None
    for bid, off, dat in _blocks(d):
        if bid == 4:
            image = dat
        elif bid == 5:
            palette = dat
    if image is None:
        return None

    fmt, order = struct.unpack_from("<HH", d, image + 4)
    w, h = struct.unpack_from("<HH", d, image + 8)
    pix = image + struct.unpack_from("<I", d, image + 0x1C)[0]

    if fmt in (4, 5):  # indexed
        bpp = 4 if fmt == 4 else 8
        width_bytes = w * bpp // 8
        raw = d[pix:pix + width_bytes * h]
        if order == 1:
            raw = _unswizzle(raw, width_bytes, h)
        b = np.frombuffer(raw, np.uint8)
        if fmt == 4:
            idx = np.empty(w * h, np.uint8)
            idx[0::2] = b & 0xF
            idx[1::2] = b >> 4
        else:
            idx = b[:w * h]
        if palette is None:
            raise ValueError("indexed image without palette block")
        pfmt = struct.unpack_from("<H", d, palette + 4)[0]
        pcount = struct.unpack_from("<H", d, palette + 8)[0]
        poff = palette + struct.unpack_from("<I", d, palette + 0x1C)[0]
        ent = 4 if pfmt == 3 else 2
        pv = np.frombuffer(d[poff:poff + pcount * ent], "<u4" if ent == 4 else "<u2")
        clut = _decode_direct(pfmt, pv)
        rgba = clut[idx].reshape(h, w, 4)
    else:              # direct colour
        ent = 4 if fmt == 3 else 2
        width_bytes = w * ent
        raw = d[pix:pix + width_bytes * h]
        if order == 1:
            raw = _unswizzle(raw, width_bytes, h)
        pv = np.frombuffer(raw, "<u4" if ent == 4 else "<u2")
        rgba = _decode_direct(fmt, pv[:w * h]).reshape(h, w, 4)

    return Image.fromarray(rgba, "RGBA")


def convert(path: Path, out: Path) -> bool:
    img = decode_gim(path.read_bytes())
    if img is None:
        print(f"  {path.name}: no image block")
        return False
    img.save(out)
    print(f"  {path.name} -> {out.name}  ({img.width}x{img.height})")
    return True


_PATH_RE = re.compile(rb"[A-Za-z]:\\[ -~]{3,120}?\.gim")


def batch_wad(blob_path: Path, outdir: Path) -> None:
    """Decode every texture in a decompressed WAD payload, STRUCT-LOCKED.

    Each texture is one record:  [u32 hash]["X:\\...\\name.gim\0"] ... [MIG block]
    where the MIG pixel block starts ~0xBC after the path-string start, and the
    u32 just before the drive letter is the material hash the GDE submesh table
    (mesh table @+0x14) references. So hash <-> name <-> pixels are all bound in
    one record: walk the path strings, and each one's texture is the first MIG
    after it.

    Do NOT name by "nearest .gim to a MIG" -- the path sits *before* its MIG, so a
    forward search grabs the NEXT texture's name and shifts/swaps labels across the
    whole set (the old bug that made furrow.png hold grassfringe02's pixels, etc.).

    Also writes manifest.json: [{hash, name, gim, mig_off, w, h}] -- the exact
    lookup gde_to_glb.py uses to texture each submesh by its hash.
    """
    d = blob_path.read_bytes()
    outdir.mkdir(parents=True, exist_ok=True)
    migs = [m.start() for m in re.finditer(re.escape(MIG_SIG), d)]

    def next_mig(o: int) -> int:
        return min((m for m in migs if m > o), default=len(d))

    ok = fail = 0
    manifest = []
    for m in _PATH_RE.finditer(d):
        s = m.start()
        gim = d[s:m.end()].split(b"\\")[-1].decode("latin1", "replace")
        h = struct.unpack_from("<I", d, s - 4)[0]
        mo = next_mig(s)
        end = next_mig(mo)
        stem = gim[:-4] if gim.lower().endswith(".gim") else gim
        stem = "".join(c if c.isalnum() or c in "_-." else "_" for c in stem) or f"tex_{mo:06x}"
        try:
            img = decode_gim(d[mo:end])
            if img is None:
                fail += 1
                continue
            img.save(outdir / f"{stem}.png")
            manifest.append({"hash": f"{h:08x}", "name": stem, "gim": gim,
                             "mig_off": mo, "w": img.width, "h": img.height})
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  FAIL {gim} @0x{mo:x}: {type(e).__name__}: {e}")
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"Done. {ok} textures decoded, {fail} failed -> {outdir}")
    print(f"Manifest: {outdir / 'manifest.json'} ({len(manifest)} hash-keyed entries)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp", type=Path, help="a .gim file, a directory of them, or (with --wad) a decompressed WAD payload")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--wad", action="store_true", help="Treat input as a decompressed WAD; decode every embedded MIG texture")
    args = ap.parse_args()
    if args.wad:
        batch_wad(args.inp, args.out)
    elif args.inp.is_dir():
        args.out.mkdir(parents=True, exist_ok=True)
        n = ok = 0
        for f in sorted(args.inp.glob("*.gim")):
            n += 1
            try:
                ok += convert(f, args.out / (f.stem + ".png"))
            except Exception as e:
                print(f"  {f.name}: FAIL {type(e).__name__}: {e}")
        print(f"Done. {ok}/{n} textures decoded -> {args.out}")
    else:
        convert(args.inp, args.out)


if __name__ == "__main__":
    main()
