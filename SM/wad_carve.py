#!/usr/bin/env python3
import sys
from pathlib import Path

# Known / suspected signatures to hunt for, to be expanded
SIGNATURES = {
    b"COL ": "collision",
    b"TIE ": "tie",
    b"BOG ": "bog",
    b"MIG.00.1PSP": "mig",
    b"SHRB": "shrub",
    b"MP": "mp_misc",
}

MIN_CHUNK_SIZE = 0x100  # sanity threshold


def find_signatures(data: bytes):
    hits = []
    for sig, name in SIGNATURES.items():
        start = 0
        while True:
            off = data.find(sig, start)
            if off == -1:
                break
            hits.append((off, sig, name))
            start = off + 1
    return sorted(hits)


def carve_chunks(data: bytes, hits):
    outdir = Path("carved")
    outdir.mkdir(exist_ok=True)

    for i, (off, sig, name) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(data)
        size = end - off
        if size < MIN_CHUNK_SIZE:
            continue

        fname = outdir / f"{off:08X}_{name}.bin"
        with open(fname, "wb") as f:
            f.write(data[off:end])

        print(f"Wrote {fname} ({size:#x} bytes)")


def main():
    if len(sys.argv) != 2:
        print("usage: wad_carve.py <decompressed_wad.bin>")
        sys.exit(1)

    path = Path(sys.argv[1])
    data = path.read_bytes()

    hits = find_signatures(data)
    print(f"Found {len(hits)} signature hits")

    for off, sig, name in hits:
        print(f"{off:08X} {name} {sig}")

    carve_chunks(data, hits)


if __name__ == "__main__":
    main()
