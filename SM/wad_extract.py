#!/usr/bin/env python3
"""
wad_extract.py - Decompress HIG! WADs and extract assets by keyword.

Subcommands:
- decompress
- list-audio
- extract-audio
- extract-textures
- extract-all
"""

from __future__ import annotations

import argparse
from pathlib import Path

from higwad import decompress_wad
from vag import iter_vags, extract_vag, decode_vag_to_pcm16, write_wav
from mig_gim import find_gim_by_keyword, extract_mig
from strings_util import find_keyword_strings


def cmd_decompress(args: argparse.Namespace) -> None:
    out, info = decompress_wad(str(args.wad))
    Path(args.out).write_bytes(out)
    print(f"Decompressed {args.wad} -> {args.out}")
    print(f"header_size=0x{info.header_size:x} comp_off=0x{info.comp_off:x} delta=0x{info.stream_delta:x} decomp_size=0x{info.decomp_size:x}")


def cmd_list_audio(args: argparse.Namespace) -> None:
    blob, _ = decompress_wad(str(args.wad))
    key = args.keyword.lower()
    hits = [v for v in iter_vags(blob) if key in (v.name or '').lower()]
    for v in hits:
        print(f"0x{v.off:08x}  {v.sample_rate:5d}Hz  size=0x{v.data_size:x}  name={v.name}")
    print(f"Found {len(hits)} matching VAG streams.")


def cmd_search_strings(args: argparse.Namespace) -> None:
    blob, _ = decompress_wad(str(args.wad))
    hits = find_keyword_strings(blob, args.keyword, case_insensitive=not args.case_sensitive)
    for h in hits[:args.limit]:
        print(f"0x{h.off:08x}  {h.text}")
    print(f"Found {len(hits)} matching printable strings (showing up to {min(len(hits), args.limit)}).")


def cmd_list_textures(args: argparse.Namespace) -> None:
    blob, _ = decompress_wad(str(args.wad))
    entries = find_gim_by_keyword(blob, args.keyword)
    for e in entries:
        print(f"0x{e.mig_off:08x}  size=0x{e.size:x}  {e.filename}")
    print(f"Found {len(entries)} matching GIM/MIG textures.")


def cmd_extract_audio(args: argparse.Namespace) -> None:
    blob, _ = decompress_wad(str(args.wad))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    key = args.keyword.lower()
    hits = [v for v in iter_vags(blob) if key in (v.name or '').lower()]
    if not hits:
        print("No matching VAG streams found.")
        return

    for v in hits:
        vag_bytes = extract_vag(blob, v)
        name = v.name if v.name else f"vag_{v.off:08x}"
        name = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in name)
        vag_path = outdir / f"{name}.vag"
        vag_path.write_bytes(vag_bytes)
        print(f"Wrote {vag_path}")

        if args.wav:
            pcm, sr = decode_vag_to_pcm16(vag_bytes)
            wav_path = outdir / f"{name}.wav"
            write_wav(str(wav_path), pcm, sr)
            print(f"Wrote {wav_path}")

    print(f"Extracted {len(hits)} VAG streams to {outdir}")


def cmd_extract_textures(args: argparse.Namespace) -> None:
    blob, _ = decompress_wad(str(args.wad))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    entries = find_gim_by_keyword(blob, args.keyword)
    if not entries:
        print("No matching GIM/MIG textures found.")
        return

    for i, e in enumerate(entries, start=1):
        mig = extract_mig(blob, e)
        base = Path(e.filename).name.replace("\\", "_").replace("/", "_")
        if not base.lower().endswith(".gim"):
            base = f"texture_{i}.gim"
        out_path = outdir / base
        if out_path.exists():
            out_path = outdir / f"{out_path.stem}_{i}{out_path.suffix}"
        out_path.write_bytes(mig)
        print(f"Wrote {out_path}  (from MIG @0x{e.mig_off:x}, size=0x{e.size:x})")


def cmd_extract_all(args: argparse.Namespace) -> None:
    blob, _ = decompress_wad(str(args.wad))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    key = args.keyword.lower()

    audio_hits = [v for v in iter_vags(blob) if key in (v.name or '').lower()]
    for v in audio_hits:
        vag_bytes = extract_vag(blob, v)
        name = v.name if v.name else f"vag_{v.off:08x}"
        name = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in name)
        (outdir / f"{name}.vag").write_bytes(vag_bytes)
        if args.wav:
            pcm, sr = decode_vag_to_pcm16(vag_bytes)
            write_wav(str(outdir / f"{name}.wav"), pcm, sr)
        print(f"Wrote {outdir / f'{name}.vag'}" + (" (+wav)" if args.wav else ""))

    tex_entries = find_gim_by_keyword(blob, args.keyword)
    for i, e in enumerate(tex_entries, start=1):
        mig = extract_mig(blob, e)
        base = Path(e.filename).name.replace("\\", "_").replace("/", "_")
        if not base.lower().endswith(".gim"):
            base = f"texture_{i}.gim"
        out_path = outdir / base
        if out_path.exists():
            out_path = outdir / f"{out_path.stem}_{i}{out_path.suffix}"
        out_path.write_bytes(mig)
        print(f"Wrote {out_path}")

    print(f"Done. Audio={len(audio_hits)} textures={len(tex_entries)} output={outdir}")


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_d = sub.add_parser("decompress", help="Decompress WAD to raw payload blob")
    ap_d.add_argument("wad")
    ap_d.add_argument("-o", "--out", required=True)
    ap_d.set_defaults(func=cmd_decompress)

    ap_la = sub.add_parser("list-audio", help="List VAG streams matching KEYWORD")
    ap_la.add_argument("wad")
    ap_la.add_argument("keyword")
    ap_la.set_defaults(func=cmd_list_audio)

    ap_ss = sub.add_parser("search-strings", help="Search printable ASCII strings in the decompressed payload")
    ap_ss.add_argument("wad")
    ap_ss.add_argument("keyword")
    ap_ss.add_argument("--limit", type=int, default=50, help="Max lines to print")
    ap_ss.add_argument("--case-sensitive", action="store_true")
    ap_ss.set_defaults(func=cmd_search_strings)

    ap_lt = sub.add_parser("list-textures", help="List .gim/MIG textures whose filename contains KEYWORD")
    ap_lt.add_argument("wad")
    ap_lt.add_argument("keyword")
    ap_lt.set_defaults(func=cmd_list_textures)

    ap_ea = sub.add_parser("extract-audio", help="Extract VAG streams matching KEYWORD")
    ap_ea.add_argument("wad")
    ap_ea.add_argument("keyword")
    ap_ea.add_argument("-o", "--out", required=True)
    ap_ea.add_argument("--wav", action="store_true")
    ap_ea.set_defaults(func=cmd_extract_audio)

    ap_et = sub.add_parser("extract-textures", help="Extract GIM/MIG textures matching KEYWORD")
    ap_et.add_argument("wad")
    ap_et.add_argument("keyword")
    ap_et.add_argument("-o", "--out", required=True)
    ap_et.set_defaults(func=cmd_extract_textures)

    ap_all = sub.add_parser("extract-all", help="Extract audio + textures matching KEYWORD")
    ap_all.add_argument("wad")
    ap_all.add_argument("keyword")
    ap_all.add_argument("-o", "--out", required=True)
    ap_all.add_argument("--wav", action="store_true")
    ap_all.set_defaults(func=cmd_extract_all)

    return ap


def main() -> None:
    ap = build_argparser()
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
