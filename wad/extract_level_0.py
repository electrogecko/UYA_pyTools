# This only extracts levels, not scenes or sound
import os, mmap, struct, shutil, stat

SECTOR = 2048 # Typicaal CD ROM Sector Size
HDR80  = b"\x80\x00\x00\x00" # Header marker
SENT   = bytes.fromhex("00 00 80 3F 00 FE FF 46 " + "CD "*56) # Keying off this thing 

ISOS = [
    # r"H:\path\to\disk1.iso",
    r"H:\path\to\disk2.iso",
]
OUTROOT = r"H:\out\packer_folder"
UNPACK_SRC = os.path.join(os.getcwd(), "unpack.sh")  # must exist

def next_hdr_after(mm, start):
    n = len(mm); lba = (start // SECTOR) + 1
    while True:
        pos = lba * SECTOR
        if pos + 4 >= n: return n
        if mm[pos:pos+4] == HDR80: return pos
        lba += 1

def write_unpack(dst_dir, level_id):
    # For convenience, this stores a copy of your unpacker script into dst_dir and set line 3 to LEVEL_ID=<id>.
    dst = os.path.join(dst_dir, "unpack.sh")
    shutil.copyfile(UNPACK_SRC, dst)
    # Normalize newlines and edit line 3 (index 2).
    with open(dst, "r", newline="") as f:
        lines = f.read().splitlines()
    while len(lines) < 3:
        lines.append("")
    lines[2] = f"LEVEL_ID={level_id}"
    with open(dst, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    # Make executable on POSIX
    try:
        st = os.stat(dst)
        os.chmod(dst, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass

os.makedirs(OUTROOT, exist_ok=True)

for iso in ISOS:
    base = os.path.splitext(os.path.basename(iso))[0]
    outdir = os.path.join(OUTROOT, base)
    os.makedirs(outdir, exist_ok=True)

    with open(iso, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        pos = mm.find(SENT)
        if pos == -1:
            print(f"[{base}] no SENT pattern")
            continue

        seen_starts = set(); idx = 0
        while pos != -1:
            lba_hit = pos // SECTOR
            sector_lo = lba_hit * SECTOR
            # anchor to true header at sector start or previous sector
            if mm[sector_lo:sector_lo+4] != HDR80:
                prev = sector_lo - SECTOR
                if prev >= 0 and mm[prev:prev+4] == HDR80:
                    sector_lo = prev
                else:
                    pos = mm.find(SENT, pos + 1)
                    continue

            sector_hi = next_hdr_after(mm, sector_lo)
            size = sector_hi - sector_lo
            if size <= 0:
                pos = mm.find(SENT, pos + 1)
                continue

            if sector_lo in seen_starts:
                pos = mm.find(SENT, pos + 1)
                continue
            seen_starts.add(sector_lo)

            # per-level folder and file
            level_dir = os.path.join(outdir, f"level{idx}")
            os.makedirs(level_dir, exist_ok=True)
            outpath = os.path.join(level_dir, f"level{idx}.0.wad")
            with open(outpath, "wb") as out:
                out.write(mm[sector_lo:sector_hi])

            # copy and edit unpack.sh. If you dont have one, ignore. 
            if os.path.isfile(UNPACK_SRC):
                write_unpack(level_dir, idx)
            else:
                print(f"[warn] unpack.sh not found at {UNPACK_SRC}")

            print(f"[{base}] wrote {os.path.relpath(outpath, OUTROOT)}  {size//1024}KB  "
                  f"LBA={sector_lo//SECTOR}..{sector_hi//SECTOR}")
            idx += 1

            pos = mm.find(SENT, pos + 1)
