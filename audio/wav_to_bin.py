#!/usr/bin/env python3
"""Convert 16-bit PCM WAV to PSX/PS2 SPU ADPCM .bin (VAG-style frames)."""

from __future__ import annotations

import argparse
import math
import struct
import sys
import wave
from pathlib import Path

COEFFS = (
    (0, 0),
    (60, 0),
    (115, -52),
    (98, -55),
    (122, -60),
)


def clamp16(v: int) -> int:
    return -32768 if v < -32768 else (32767 if v > 32767 else v)


def round_away_from_zero(v: float) -> int:
    if v >= 0:
        return int(math.floor(v + 0.5))
    return int(math.ceil(v - 0.5))


def read_wav_samples(path: Path, channel: int, mixdown: bool) -> list[int]:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        frames = wf.getnframes()
        if sampwidth != 2:
            raise ValueError(f"Expected 16-bit WAV, got {sampwidth * 8}-bit")
        if channels < 1:
            raise ValueError("WAV has no channels")
        if not mixdown and not (0 <= channel < channels):
            raise ValueError(f"Channel index {channel} out of range for {channels} channels")

        raw = wf.readframes(frames)
        all_samples = struct.unpack("<" + "h" * (frames * channels), raw)

        out: list[int] = []
        if channels == 1:
            out.extend(all_samples)
        elif mixdown:
            for i in range(frames):
                base = i * channels
                s = sum(all_samples[base + c] for c in range(channels))
                out.append(int(round(s / channels)))
        else:
            for i in range(frames):
                out.append(all_samples[i * channels + channel])
        return out


def encode_frame(samples28: list[int], hist1: int, hist2: int) -> tuple[int, bytes, int, int]:
    best_err = None
    best_header = 0
    best_payload = b""
    best_h1 = hist1
    best_h2 = hist2

    for pred_idx, (c0, c1) in enumerate(COEFFS):
        for shift in range(13):
            h1 = hist1
            h2 = hist2
            nibbles: list[int] = []
            err = 0

            for target in samples28:
                predicted = ((h1 * c0) + (h2 * c1) + 32) >> 6
                residual = target - predicted
                q = round_away_from_zero((residual * (1 << shift)) / 4096.0)
                if q < -8:
                    q = -8
                elif q > 7:
                    q = 7

                decoded = predicted + ((q << 12) >> shift)
                decoded = clamp16(decoded)
                diff = target - decoded
                err += diff * diff
                h2 = h1
                h1 = decoded
                nibbles.append(q & 0x0F)

            if best_err is None or err < best_err:
                frame_bytes = bytearray(14)
                for i in range(14):
                    lo = nibbles[i * 2]
                    hi = nibbles[i * 2 + 1]
                    frame_bytes[i] = lo | (hi << 4)
                best_err = err
                best_header = (pred_idx << 4) | shift
                best_payload = bytes(frame_bytes)
                best_h1 = h1
                best_h2 = h2

    return best_header, best_payload, best_h1, best_h2


def encode_bin(samples: list[int], prepend_zero_frame: bool, set_end_flag: bool) -> bytes:
    out = bytearray()
    if prepend_zero_frame:
        out.extend(b"\x00" * 16)

    total_frames = (len(samples) + 27) // 28
    hist1 = 0
    hist2 = 0

    for frame_idx in range(total_frames):
        start = frame_idx * 28
        chunk = samples[start : start + 28]
        if len(chunk) < 28:
            chunk = chunk + [0] * (28 - len(chunk))

        header, payload, hist1, hist2 = encode_frame(chunk, hist1, hist2)
        flags = 0
        if set_end_flag and frame_idx == total_frames - 1:
            flags |= 0x01
        out.append(header)
        out.append(flags)
        out.extend(payload)

    return bytes(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert WAV to PSX/PS2 SPU ADPCM .bin")
    parser.add_argument("input_wav", type=Path, help="Input WAV (16-bit PCM)")
    parser.add_argument("output_bin", type=Path, help="Output .bin path")
    parser.add_argument("--channel", type=int, default=0, help="Channel to use if not mixing down (default: 0)")
    parser.add_argument("--mixdown", action="store_true", help="Average all channels to mono before encoding")
    parser.add_argument(
        "--prepend-zero-frame",
        action="store_true",
        help="Prepend one 16-byte all-zero frame",
    )
    parser.add_argument(
        "--no-end-flag",
        action="store_true",
        help="Do not set bit0 end flag on the final ADPCM frame",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        samples = read_wav_samples(args.input_wav, args.channel, args.mixdown)
        if not samples:
            raise ValueError("Input WAV has zero samples")
        data = encode_bin(
            samples=samples,
            prepend_zero_frame=args.prepend_zero_frame,
            set_end_flag=(not args.no_end_flag),
        )
        args.output_bin.write_bytes(data)
        print(f"Wrote {len(data)} bytes to {args.output_bin}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
