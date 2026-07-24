#!/usr/bin/env python3
"""TJZIP / HIG! WAD decompressor.

Implements the byte-oriented TJZIP decoder used

  - TJZIP_ParseRawDataBlock__FPPUcT0PUi
  - TJZIP_ParseDictionaryCode__FPPUcT0PUi
  - TJZIP_Decompress__FPUcT0UiPUiT0PFPUc_PUc

This tool dumps the fully-decompressed payload from a single-file "HIG!" WAD.
It handles the observed WAD variants, including the ETC/merged WADs (GLOBAL /
MULTIPLAYER / SINGLEPLAYER). It does not attempt post-processing/fixups.

Usage examples:
  python3 tjzip_dump.py /path/to/17.WAD -o out.bin
  python3 tjzip_dump.py /path/to/GLOBAL.WAD -o out.bin --verify /path/to/known_out.bin

Notes:
  - The TJZIP bitstream start is derived from the header layout (see
    parse_hig_wad). It is NOT the u32 at +0x04 -- that field is 0 on the ETC
    WADs and 0x10C0 on per-level WADs, and was never a header size.
  - Decompression stops when it has emitted `decomp_size` (from +0x3C) bytes,
    not when the input is exhausted; streams are padded past the last token.
  - CRC computation is optional. If you have a CRC table dump, you can wire it
    in via --crc-table (ASCII hex byte pairs or a raw 1024-byte table). The
    result matches the CRC32 stored at header +0x34.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path
from typing import Optional, Tuple, List


HEADER_MAGIC = b"HIG!"


class TJZIPError(RuntimeError):
    pass


def _u32le(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


# Layout of a HIG! WAD header (confirmed on both console variants):
#   0x00  char[4]  "HIG!"
#   0x04  u32      NOT the header size. It is 0x10C0 for per-level ".mb.wad"
#                  files and 0x00000000 for the merged ETC WADs (GLOBAL /
#                  MULTIPLAYER / SINGLEPLAYER). Do not use it to locate data.
#   0x34  u32      CRC32 of the decompressed payload
#   0x38  u32      always 6 (format/version tag)
#   0x3C  u32      decompressed size
#   0x40  u32      compressed size (approx; not needed to decode)
#   0x44  char[]   NUL-terminated source ".conf" path (e.g. C:\HIG\...\*.conf)
#   ...   0x00     padding to a 0x40 alignment boundary
# The TJZIP bitstream begins immediately after that padding. For every retail
# WAD this lands at a fixed 0xC0, but we compute it from the path so
# unusually long paths still work.
HEADER_ALIGN = 0x40
HEADER_MIN = 0xC0
CONF_PATH_OFF = 0x44


def parse_hig_wad(blob: bytes, *, base_off: int = 0) -> Tuple[int, int, int]:
    """Return (header_size, comp_off, decomp_size) for a HIG! wad at base_off.

    header_size is the byte offset (relative to base_off) at which the TJZIP
    bitstream starts. It is derived from the layout, NOT read from +0x04 (that
    field is 0 on ETC/merged WADs and 0x10C0 on level WADs -- neither is a size).
    """
    if blob[base_off:base_off + 4] != HEADER_MAGIC:
        raise TJZIPError("Not a HIG! WAD at given offset")

    # Header = fixed fields + NUL-terminated .conf path, padded to HEADER_ALIGN.
    path_end = blob.find(b"\x00", base_off + CONF_PATH_OFF)
    if path_end == -1:
        raise TJZIPError("No NUL terminator after conf path field")
    header_size = ((path_end - base_off) + HEADER_ALIGN) & ~(HEADER_ALIGN - 1)
    if header_size < HEADER_MIN:
        header_size = HEADER_MIN
    if header_size > len(blob) - base_off:
        raise TJZIPError(f"Computed header_size=0x{header_size:x} past EOF")

    decomp_size = _u32le(blob, base_off + 0x3C)
    if decomp_size == 0 or decomp_size > 0x80000000:
        raise TJZIPError(f"Suspicious decomp_size=0x{decomp_size:x}")

    comp_off = base_off + header_size
    if comp_off > len(blob):
        raise TJZIPError("Compressed offset past EOF")
    return header_size, comp_off, decomp_size


def load_crc_table(path: Path) -> List[int]:
    """Load CRC table as 256 u32 entries.

    Accepts either:
      - raw 1024 bytes (little-endian u32 table)
      - ASCII whitespace-delimited hex byte pairs (e.g. "00 00 00 00 96 30 07
        77 ...", the standard CRC32 table in little-endian u32 order). Must
        decode to 1024 bytes. A "0x" prefix on each token is tolerated.
    """
    data = path.read_bytes()
    # Try raw
    if len(data) == 1024:
        return list(struct.unpack("<256I", data))
    # Try ASCII bytes
    try:
        txt = data.decode("ascii", errors="strict")
    except Exception as e:
        raise TJZIPError(f"Unsupported CRC table format: {e}")
    parts = txt.split()
    # Tokens are hex byte pairs without a prefix ("07", "96", ...); int(p, 0)
    # would reject those, so parse as base 16 (stripping an optional 0x).
    try:
        b = bytes(int(p[2:] if p.lower().startswith("0x") else p, 16) & 0xFF for p in parts)
    except ValueError as e:
        raise TJZIPError(f"ASCII CRC table must be hex byte pairs: {e}")
    if len(b) != 1024:
        raise TJZIPError(f"ASCII CRC table must decode to 1024 bytes, got {len(b)}")
    return list(struct.unpack("<256I", b))


def crc_update(crc: int, byte_val: int, table: List[int]) -> int:
    idx = (crc ^ byte_val) & 0xFF
    return ((crc >> 8) ^ table[idx]) & 0xFFFFFFFF


def tjzip_parse_raw(inbuf: bytes, inpos: int, out: bytearray, outpos: int,
                    *, crc: int, crc_table: Optional[List[int]]) -> Tuple[int, int, int]:
    """ParseRawDataBlock: copies a literal block from input to output."""
    if inpos >= len(inbuf):
        raise TJZIPError("Raw block: input underrun")
    b0 = inbuf[inpos]
    inpos += 1
    if b0 != 0:
        run_len = b0 + 2
    else:
        if inpos + 2 > len(inbuf):
            raise TJZIPError("Raw block: input underrun on u16")
        run_len = inbuf[inpos] | (inbuf[inpos + 1] << 8)
        inpos += 2

    if outpos + run_len > len(out):
        raise TJZIPError("Raw block: output overrun")
    if inpos + run_len > len(inbuf):
        raise TJZIPError("Raw block: input underrun on payload")

    if crc_table is None:
        out[outpos:outpos + run_len] = inbuf[inpos:inpos + run_len]
        return inpos + run_len, outpos + run_len, crc

    # Update CRC per-byte
    for i in range(run_len):
        v = inbuf[inpos + i]
        out[outpos + i] = v
        crc = crc_update(crc, v, crc_table)
    return inpos + run_len, outpos + run_len, crc


def tjzip_parse_dict(inbuf: bytes, inpos: int, out: bytearray, outpos: int,
                     *, crc: int, crc_table: Optional[List[int]]) -> Tuple[int, int, int, int]:
    """ParseDictionaryCode: decodes one backreference and copies it, returning (inpos,outpos,crc,post)."""
    if inpos + 2 > len(inbuf):
        raise TJZIPError("Dict: input underrun")
    b1 = inbuf[inpos]
    b2 = inbuf[inpos + 1]
    inpos += 2

    top = b1 & 0xE0
    if top < 0xC0:
        length = (b1 >> 5) + 4
        dist = ((b1 << 6) & 0x300) | b2
        post = b1 & 0x03
    elif top == 0xC0:
        if inpos >= len(inbuf):
            raise TJZIPError("Dict(C0): input underrun")
        b3 = inbuf[inpos]
        inpos += 1
        length = (b1 & 0x1F) + 4
        dist = ((b2 << 6) & 0x3F00) | b3
        post = b2 & 0x03
    else:
        # 0xE0
        if inpos >= len(inbuf):
            raise TJZIPError("Dict(E0): input underrun")
        b3 = inbuf[inpos]
        inpos += 1
        small_len = (b1 & 0x0F) + 3
        if small_len >= 4:
            length = small_len
            dist = ((b1 & 0x10) << 10) | ((b2 & 0xFC) << 6) | b3
            post = b2 & 0x03
        else:
            # extended length
            if inpos >= len(inbuf):
                raise TJZIPError("Dict(E0/ext): input underrun on b4")
            b4 = inbuf[inpos]
            inpos += 1
            length2 = b2 + 0x12
            if length2 >= 0x13:
                length = length2
                dist = ((b1 & 0x10) << 10) | ((b3 & 0xFC) << 6) | b4
                post = b3 & 0x03
            else:
                # very-extended length uses b3:b4 as length, and reads b5,b6 for distance
                if inpos + 2 > len(inbuf):
                    raise TJZIPError("Dict(E0/veryext): input underrun")
                b5 = inbuf[inpos]
                b6 = inbuf[inpos + 1]
                inpos += 2
                length = (b3 << 8) | b4
                dist = ((b1 & 0x10) << 10) | ((b5 & 0xFC) << 6) | b6
                post = b5 & 0x03

    if dist == 0:
        raise TJZIPError("Dict: zero distance")
    if dist > outpos:
        raise TJZIPError(f"Dict: backref distance {dist} beyond output pos {outpos}")
    if outpos + length > len(out):
        raise TJZIPError("Dict: output overrun")

    src = outpos - dist
    if crc_table is None:
        # bytewise copy to support overlap
        for i in range(length):
            out[outpos + i] = out[src + i]
        return inpos, outpos + length, crc, post

    for i in range(length):
        v = out[src + i]
        out[outpos + i] = v
        crc = crc_update(crc, v, crc_table)
    return inpos, outpos + length, crc, post


def tjzip_decompress(comp: bytes, decomp_size: int,
                     *, crc_table: Optional[List[int]] = None,
                     limit_out: Optional[int] = None,
                     history_size: int = 0) -> Tuple[bytes, int]:
    """Decompress TJZIP stream.

    Returns (output_bytes, final_crc) where final_crc is ~crc if crc_table provided, else 0.
    """
    # The original routine allows dictionary distances to reference memory *before*
    # the output start pointer (a classic LZ sliding-window history buffer).
    # Provide an optional zero-initialized history prefix to support those streams.
    out = bytearray(history_size + decomp_size)
    inpos = 0
    outpos = history_size
    crc = 0

    # Initial raw block
    inpos, outpos, crc = tjzip_parse_raw(comp, inpos, out, outpos, crc=crc, crc_table=crc_table)
    if limit_out is not None and outpos >= limit_out:
        return bytes(out[history_size:history_size + limit_out]), (~crc) & 0xFFFFFFFF if crc_table else 0

    # Main loop: parse dict, then optional literal/raw.
    #
    # Termination is driven by the OUTPUT length (decomp_size), not by input
    # exhaustion. The original TJZIP_Decompress is told how many bytes to emit
    # and stops as soon as it has produced them; the compressed stream is padded
    # to an alignment boundary, so a few unused input bytes remain after the last
    # real token. Looping on `inpos < len(comp)` instead would parse that padding
    # as one extra (garbage) token and underrun -- the "Raw block: input
    # underrun" failure seen on about half the WADs.
    comp_len = len(comp)
    out_end = history_size + decomp_size
    while outpos < out_end and inpos < comp_len:
        inpos, outpos, crc, post = tjzip_parse_dict(comp, inpos, out, outpos, crc=crc, crc_table=crc_table)

        if limit_out is not None and outpos >= limit_out:
            return bytes(out[history_size:history_size + limit_out]), (~crc) & 0xFFFFFFFF if crc_table else 0

        # Output complete: stop before consuming any trailing block/padding.
        if outpos >= out_end:
            break

        # IMPORTANT: per TJZIP_Decompress, post==3 means "no trailing bytes" (neither raw nor literal).
        if post == 0:
            inpos, outpos, crc = tjzip_parse_raw(comp, inpos, out, outpos, crc=crc, crc_table=crc_table)
        elif post in (1, 2):
            # copy 'post' literal bytes
            if inpos + post > comp_len:
                raise TJZIPError("Post-literal: input underrun")
            if outpos + post > len(out):
                raise TJZIPError("Post-literal: output overrun")
            if crc_table is None:
                out[outpos:outpos + post] = comp[inpos:inpos + post]
                inpos += post
                outpos += post
            else:
                for i in range(post):
                    v = comp[inpos + i]
                    out[outpos + i] = v
                    crc = crc_update(crc, v, crc_table)
                inpos += post
                outpos += post
        elif post == 3:
            pass
        else:
            raise TJZIPError(f"Unexpected post value {post}")

        if limit_out is not None and (outpos - history_size) >= limit_out:
            return bytes(out[history_size:history_size + limit_out]), (~crc) & 0xFFFFFFFF if crc_table else 0

    # Finished input. Final CRC is bitwise NOT.
    final_crc = (~crc) & 0xFFFFFFFF if crc_table else 0
    return bytes(out[history_size:history_size + decomp_size]), final_crc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wad", type=Path, help="Input HIG! WAD file")
    ap.add_argument("-o", "--out", type=Path, required=True, help="Output decompressed blob")
    ap.add_argument("--crc-table", type=Path, default=None, help="CRC table dump (optional)")
    ap.add_argument("--verify", type=Path, default=None, help="Known-good decompressed blob to compare")
    ap.add_argument("--history", type=lambda x: int(x, 0), default=0x10000,
                    help="Zero-initialized history prefix size (hex allowed). Default 0x10000")
    ap.add_argument("--include-history", action="store_true",
                    help="Write the history prefix + decompressed payload (useful for matching in-memory dumps)")
    ap.add_argument("--limit-out", type=lambda x: int(x, 0), default=None,
                    help="Stop after producing N output bytes (hex allowed)")
    args = ap.parse_args()

    blob = args.wad.read_bytes()
    header_size, comp_off, decomp_size = parse_hig_wad(blob)
    comp = blob[comp_off:]

    table = load_crc_table(args.crc_table) if args.crc_table else None
    out_bytes, final_crc = tjzip_decompress(
        comp,
        decomp_size,
        crc_table=table,
        limit_out=args.limit_out,
        history_size=args.history,
    )

    if args.include_history and args.history:
        args.out.write_bytes(b"\x00" * args.history + out_bytes)
    else:
        args.out.write_bytes(out_bytes)

    if args.verify:
        ref = args.verify.read_bytes()
        n = min(len(ref), len(out_bytes))
        if ref[:n] != out_bytes[:n] or len(ref) != len(out_bytes):
            # find first mismatch
            mm = None
            for i in range(n):
                if ref[i] != out_bytes[i]:
                    mm = i
                    break
            if mm is None and len(ref) != len(out_bytes):
                mm = n
            raise SystemExit(f"VERIFY FAILED: first mismatch at 0x{mm:x} (ref_len={len(ref)}, out_len={len(out_bytes)})")
        print("VERIFY OK")

    if table:
        print(f"Final CRC: 0x{final_crc:08x}")
    print(f"Wrote {len(out_bytes)} bytes (decomp_size=0x{decomp_size:x}, header_size=0x{header_size:x}, comp_size=0x{len(comp):x})")


if __name__ == "__main__":
    main()
