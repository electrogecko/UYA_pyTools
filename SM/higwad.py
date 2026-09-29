#!/usr/bin/env python3
"""
higwad.py - Helpers for High Impact Games WAD containers.

Handles:
- Detecting HIG! WADs
- Locating the TJZIP bitstream from the fixed header layout (see tjzip_dump.
  parse_hig_wad); no brute-force scanning is needed.
- Decompressing to a payload blob.

The heavy lifting (header parsing + TJZIP decode) lives in tjzip_dump so there
is a single, authoritative implementation. This module is a thin convenience
wrapper that returns the decompressed payload plus some diagnostic info.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from tjzip_dump import parse_hig_wad, tjzip_decompress, TJZIPError  # noqa: F401


HIG_MAGIC = b"HIG!"
HISTORY_SIZE = 0x10000


@dataclass
class HigWadInfo:
    header_size: int
    comp_off: int
    comp_size: int
    decomp_size: int
    # Retained for backwards compatibility with callers that printed a probe
    # delta. The stream start is now deterministic, so this is always 0.
    stream_delta: int = 0


def decompress_wad(path: str, *, history_size: int = HISTORY_SIZE) -> Tuple[bytes, HigWadInfo]:
    """Decompress a HIG! WAD file to its raw payload blob.

    Returns (payload_bytes, HigWadInfo).
    """
    with open(path, "rb") as f:
        blob = f.read()

    header_size, comp_off, decomp_size = parse_hig_wad(blob)
    comp = blob[comp_off:]
    out, _crc = tjzip_decompress(comp, decomp_size, history_size=history_size)

    info = HigWadInfo(
        header_size=header_size,
        comp_off=comp_off,
        comp_size=len(comp),
        decomp_size=decomp_size,
        stream_delta=0,
    )
    return out, info
