#!/usr/bin/env python3
"""
vag.py - Enumerate/extract/decode VAG (PSX ADPCM) streams.

Supports standard "VAGp" header:
- data_size (big-endian) at 0x0C
- sample_rate (big-endian) at 0x10
- name bytes at 0x20..0x30 (often truncated to 12 chars by the game)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple
import struct
import wave


@dataclass
class VagEntry:
    off: int
    name: str
    data_size: int
    sample_rate: int
    total_size: int


def iter_vags(blob: bytes, *, max_data_size: int = 0x4000000) -> Iterable[VagEntry]:
    off = 0
    sig = b"VAGp"
    while True:
        idx = blob.find(sig, off)
        if idx == -1:
            break
        if idx + 0x30 <= len(blob):
            try:
                data_size = struct.unpack(">I", blob[idx + 0x0C: idx + 0x10])[0]
                sample_rate = struct.unpack(">I", blob[idx + 0x10: idx + 0x14])[0]
                name_raw = blob[idx + 0x20: idx + 0x30]
                name = name_raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore")
                total = 0x30 + data_size
                if 0 < data_size <= max_data_size and idx + total <= len(blob):
                    yield VagEntry(idx, name, data_size, sample_rate, total)
            except Exception:
                pass
        off = idx + 4


def extract_vag(blob: bytes, entry: VagEntry) -> bytes:
    return blob[entry.off: entry.off + entry.total_size]


_COEFFS = [
    (0.0, 0.0),
    (60/64, 0.0),
    (115/64, -52/64),
    (98/64, -55/64),
    (122/64, -60/64),
]


def decode_vag_to_pcm16(vag_bytes: bytes) -> Tuple[List[int], int]:
    if vag_bytes[:4] != b"VAGp":
        raise ValueError("Not a VAGp stream")
    data_size = struct.unpack(">I", vag_bytes[0x0C:0x10])[0]
    sample_rate = struct.unpack(">I", vag_bytes[0x10:0x14])[0]
    adpcm = vag_bytes[0x30:0x30 + data_size]

    pcm: List[int] = []
    s1 = 0.0
    s2 = 0.0

    for i in range(0, len(adpcm), 16):
        block = adpcm[i:i + 16]
        if len(block) < 16:
            break
        predict = block[0] >> 4
        shift = block[0] & 0x0F
        f1, f2 = _COEFFS[predict] if predict < len(_COEFFS) else (0.0, 0.0)

        for b in block[2:16]:
            for nibble in ((b >> 4) & 0x0F, b & 0x0F):
                sample = nibble if nibble < 8 else nibble - 16
                sample = (sample << 12) >> shift
                sample = sample + s1 * f1 + s2 * f2
                s2 = s1
                s1 = sample
                si = int(sample)
                if si < -32768: si = -32768
                if si > 32767: si = 32767
                pcm.append(si)

    return pcm, sample_rate


def write_wav(path: str, pcm: List[int], sample_rate: int) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h"*len(pcm), *pcm))
