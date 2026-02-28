#!/usr/bin/env python3
"""Convert PSX/PS2 SPU ADPCM .bin (VAG-style frames) to 16-bit PCM WAV."""

from __future__ import annotations

import argparse
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


def decode_frame(frame: bytes, hist1: int, hist2: int) -> tuple[list[int], int, int, int]:
    if len(frame) != 16:
        raise ValueError("Frame must be exactly 16 bytes")

    header = frame[0]
    flags = frame[1]
    pred = (header >> 4) & 0x0F
    shift = header & 0x0F
    if pred >= len(COEFFS):
        pred = 0
    if shift > 12:
        shift = 12
    c0, c1 = COEFFS[pred]

    out: list[int] = []
    for i in range(28):
        b = frame[2 + (i // 2)]
        nib = (b & 0x0F) if (i % 2 == 0) else ((b >> 4) & 0x0F)
        if nib >= 8:
            nib -= 16
        predicted = ((hist1 * c0) + (hist2 * c1) + 32) >> 6
        sample = predicted + ((nib << 12) >> shift)
        sample = clamp16(sample)
        out.append(sample)
        hist2 = hist1
        hist1 = sample

    return out, hist1, hist2, flags


def decode_bin(data: bytes, decode_all: bool, drop_leading_zero_frame: bool) -> list[int]:
    if len(data) % 16 != 0:
        raise ValueError(f"Input size must be multiple of 16 bytes, got {len(data)}")

    hist1 = 0
    hist2 = 0
    samples: list[int] = []
    frames = len(data) // 16
    for i in range(frames):
        frame = data[i * 16 : (i + 1) * 16]
        decoded, hist1, hist2, flags = decode_frame(frame, hist1, hist2)
        samples.extend(decoded)
        if (flags & 0x01) and not decode_all:
            break

    if drop_leading_zero_frame and len(samples) >= 28 and all(s == 0 for s in samples[:28]):
        samples = samples[28:]

    return samples


def write_wav(path: Path, samples: list[int], sample_rate: int) -> None:
    raw = struct.pack("<" + "h" * len(samples), *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert PSX/PS2 SPU ADPCM .bin to WAV")
    parser.add_argument("input_bin", type=Path, help="Input .bin path")
    parser.add_argument("output_wav", type=Path, help="Output WAV path")
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=22050,
        help="Output WAV sample rate (default: 22050). BIN does not store this.",
    )
    parser.add_argument(
        "--decode-all",
        action="store_true",
        help="Decode every frame instead of stopping at end-flag bit0",
    )
    parser.add_argument(
        "--drop-leading-zero-frame",
        action="store_true",
        help="Drop first decoded frame if all 28 samples are zero",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.sample_rate <= 0:
            raise ValueError("sample-rate must be > 0")
        data = args.input_bin.read_bytes()
        samples = decode_bin(
            data=data,
            decode_all=args.decode_all,
            drop_leading_zero_frame=args.drop_leading_zero_frame,
        )
        write_wav(args.output_wav, samples, args.sample_rate)
        print(f"Wrote {len(samples)} samples to {args.output_wav}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
