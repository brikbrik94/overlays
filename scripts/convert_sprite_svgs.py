#!/usr/bin/env python3
"""Convert SVG sprite sources to PNG files for sprite sheet generation.

Default behavior:
- read SVG files from assets/sprites recursively
- write PNG files to assets/sprites/png (same relative structure)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def discover_svgs(source: Path) -> list[Path]:
    return sorted(path for path in source.rglob('*.svg') if path.is_file())




def maybe_rerun_in_local_venv() -> int | None:
    repo_root = Path(__file__).resolve().parent.parent
    venv_python = repo_root / ".venv" / "bin" / "python"
    current_python = Path(sys.executable).resolve()
    if not venv_python.exists() or current_python == venv_python.resolve():
        return None

    cmd = [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]]
    print(f"cairosvg not found in current interpreter; retrying with {venv_python}")
    return subprocess.run(cmd, check=False).returncode


def convert_one(svg_path: Path, source_root: Path, out_root: Path, scale: float) -> Path:
    import cairosvg

    rel = svg_path.relative_to(source_root)
    out_path = (out_root / rel).with_suffix('.png')
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(out_path),
        scale=scale,
    )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Convert SVG sprite assets to PNG files.')
    parser.add_argument('--source', default='assets/sprites', help='Source directory containing SVG files.')
    parser.add_argument('--out', default='assets/sprites/png', help='Output directory for converted PNG files.')
    parser.add_argument('--scale', type=float, default=1.0, help='Rasterization scale passed to cairosvg.')
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()

    svgs = discover_svgs(source)
    if not svgs:
        print(f'no SVG files found under {source}; nothing to convert')
        return 0

    try:
        converted = [convert_one(svg, source, out, args.scale) for svg in svgs]
    except ModuleNotFoundError as exc:
        rerun_code = maybe_rerun_in_local_venv()
        if rerun_code is not None:
            return rerun_code
        raise SystemExit(
            'cairosvg is required for SVG conversion. Run `bash scripts/install_python_deps.sh` '
            'and execute this script via `.venv/bin/python` or an activated venv. '
            'If system Cairo libs are missing, install them on your build host.'
        ) from exc

    print(f'converted {len(converted)} SVG files into {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
