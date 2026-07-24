#!/usr/bin/env python3
"""strings_util.py - printable ASCII string scanning helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple
import re


@dataclass
class FoundString:
    off: int
    text: str


def iter_printable_strings(blob: bytes, *, min_len: int = 5) -> Iterable[FoundString]:
    pat = re.compile(rb"[ -~]{%d,}" % max(1, min_len))
    for m in pat.finditer(blob):
        yield FoundString(m.start(), m.group(0).decode("ascii", errors="ignore"))


def find_cstring_around(blob: bytes, pos: int, *, max_len: int = 512) -> Tuple[int, int, str]:
    start = pos
    while start > 0 and 32 <= blob[start - 1] < 127 and (pos - start) < max_len:
        start -= 1
    end = pos
    while end < len(blob) and 32 <= blob[end] < 127 and (end - pos) < max_len:
        end += 1
    s = blob[start:end].decode("ascii", errors="ignore")
    return start, end, s


def find_keyword_strings(blob: bytes, keyword: str, *, case_insensitive: bool = True) -> List[FoundString]:
    key = keyword.lower() if case_insensitive else keyword
    out: List[FoundString] = []
    for fs in iter_printable_strings(blob, min_len=5):
        hay = fs.text.lower() if case_insensitive else fs.text
        if key in hay:
            out.append(fs)
    return out
