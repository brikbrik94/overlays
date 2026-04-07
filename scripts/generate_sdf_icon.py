#!/usr/bin/env python3
import argparse, math, struct, zlib
from pathlib import Path
from typing import Iterable

def sd_rounded_box(px: float, py: float, hx: float, hy: float, radius: float) -> float:
    qx, qy = abs(px) - (hx - radius), abs(py) - (hy - radius)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - radius

def write_png_rgba(path: Path, width: int, height: int, pixels: Iterable[bytes]) -> None:
    def chunk(tag, data): return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + row for row in pixels)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="assets/sprites/sdf/label-bubble-sdf.png")
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--radius", type=float, default=32.0)
    parser.add_argument("--spread", type=float, default=18.0)
    args = parser.parse_args()
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    cx, cy = (args.width - 1) / 2.0, (args.height - 1) / 2.0
    hx, hy = args.width / 2.0 - 1.0, args.height / 2.0 - 1.0
    for y in range(args.height):
        row = bytearray()
        for x in range(args.width):
            sd = sd_rounded_box(x - cx, y - cy, hx, hy, args.radius)
            alpha = int(round(max(0.0, min(1.0, 0.5 - (sd / args.spread))) * 255.0))
            row.extend((255, 255, 255, alpha))
        rows.append(bytes(row))
    write_png_rgba(out_path, args.width, args.height, rows)
    print(f"Wrote {out_path}")

if __name__ == "__main__": main()
