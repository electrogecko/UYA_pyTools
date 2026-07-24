#!/usr/bin/env python3
"""
mig_gim.py - Extract GIM container blobs from decompressed WAD payloads.

Finds .gim filename strings matching a keyword, then locates nearby container
headers and extracts the blob.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import struct


MIG_SIG = bytes.fromhex("4D 49 47 2E 30 30 2E 31 50 53 50")


@dataclass
class MigEntry:
    mig_off: int
    size: int
    str_off: int
    filename: str


def _u32le(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _parse_mig_size(blob: bytes, mig_off: int) -> Optional[int]:
    for rel in (0x14, 0x10):
        if mig_off + rel + 4 <= len(blob):
            size = _u32le(blob, mig_off + rel)
            if 0 < size <= 0x20000000 and (mig_off + size) <= len(blob):
                return size
    return None


def find_gim_by_keyword(blob: bytes, keyword: str, *, window: int = 0x4000, case_insensitive: bool = True) -> List[MigEntry]:
    key = keyword.lower() if case_insensitive else keyword
    out: List[MigEntry] = []
    lower = blob.lower() if case_insensitive else blob

    needle = b".gim"
    start = 0
    while True:
        i = lower.find(needle, start)
        if i == -1:
            break

        s0 = i
        while s0 > 0 and 32 <= blob[s0 - 1] < 127 and (i - s0) < 256:
            s0 -= 1
        s1 = i + len(needle)
        while s1 < len(blob) and 32 <= blob[s1] < 127 and (s1 - i) < 256:
            s1 += 1

        filename = blob[s0:s1].decode("ascii", errors="ignore")
        hay = filename.lower() if case_insensitive else filename

        if key in hay:
            fwd = blob.find(MIG_SIG, i, min(len(blob), i + window))
            bwd = blob.rfind(MIG_SIG, max(0, i - window), i)
            mig_off = fwd if fwd != -1 else bwd
            if mig_off != -1:
                size = _parse_mig_size(blob, mig_off)
                if size is not None:
                    out.append(MigEntry(mig_off=mig_off, size=size, str_off=s0, filename=filename))

        start = i + 1

    seen = set()
    uniq: List[MigEntry] = []
    for e in out:
        if e.mig_off in seen:
            continue
        seen.add(e.mig_off)
        uniq.append(e)
    return uniq


def extract_mig(blob: bytes, entry: MigEntry) -> bytes:
    return blob[entry.mig_off: entry.mig_off + entry.size]
