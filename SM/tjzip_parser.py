
# tjzip_parser.py
# TJZIP parser based on SCUS_976.15 disassembly
# Includes:
# - Correct dictionary token decoding
# - 0x8000-byte history window
# - Standard CRC32 table (matches SCUS table)
# - Diagnostic-friendly structure

import struct

HISTORY_SIZE = 0x8000

def build_crc32_table():
    poly = 0xEDB88320
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly if (c & 1) else (c >> 1)
        table.append(c & 0xFFFFFFFF)
    return table

CRC_TABLE = build_crc32_table()

def parse_raw(src, sptr, out):
    count = src[sptr]
    sptr += 1
    out.extend(src[sptr:sptr+count])
    return sptr + count

def parse_dict(src, sptr, out):
    b1 = src[sptr]; sptr += 1
    top = b1 & 0xE0

    if top == 0x00:
        # short form
        b2 = src[sptr]; sptr += 1
        length = (b1 >> 2) + 2
        offset = ((b1 & 0x03) << 8) | b2

    elif top == 0xC0:
        # medium form
        b2 = src[sptr]; sptr += 1
        b3 = src[sptr]; sptr += 1
        length = (b1 & 0x1F) + 3
        offset = (b2 << 8) | b3

    elif top == 0xE0:
        # long / extended form
        b2 = src[sptr]; sptr += 1
        length = (b1 & 0x1F) + 3
        if b2 == 0:
            length += src[sptr]
            sptr += 1
            b2 = src[sptr]; sptr += 1
        b3 = src[sptr]; sptr += 1
        offset = (b2 << 8) | b3

    else:
        raise RuntimeError(f"Unknown dict token {b1:02X}")

    src_pos = len(out) - offset
    if src_pos < 0:
        raise RuntimeError(f"Backref underflow: offset={offset}, out={len(out)}")

    for _ in range(length):
        out.append(out[src_pos])
        src_pos += 1

    return sptr

def tjzip_decompress(src):
    sptr = 0
    out = bytearray(b'\x00' * HISTORY_SIZE)

    while sptr < len(src):
        ctrl = src[sptr]
        sptr += 1

        for i in range(8):
            if ctrl & (1 << i):
                sptr = parse_dict(src, sptr, out)
            else:
                sptr = parse_raw(src, sptr, out)

            if sptr >= len(src):
                break

    return out[HISTORY_SIZE:]

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: tjzip_parser_fixed.py <input.bin> <output.bin>")
        sys.exit(1)

    data = open(sys.argv[1], "rb").read()
    out = tjzip_decompress(data)
    open(sys.argv[2], "wb").write(out)
    print("Done")
