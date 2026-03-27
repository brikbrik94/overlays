#!/usr/bin/env python3
"""Build simple MapLibre sprite sheets from PNG icon sources.

Expected input structure (recommended):
  assets/sprites/<group>/*.png

For each <group>, the script writes:
  <out>/<group>.json
  <out>/<group>.png
  <out>/<group>@2x.json
  <out>/<group>@2x.png
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class IconSpec:
    name: str
    path: Path


def discover_groups(source: Path) -> Dict[str, List[IconSpec]]:
    groups: Dict[str, List[IconSpec]] = {}
    for png in sorted(source.rglob("*.png")):
        if not png.is_file():
            continue
        rel = png.relative_to(source)
        group = rel.parts[0] if len(rel.parts) > 1 else "default"
        icon_name = png.stem
        groups.setdefault(group, []).append(IconSpec(name=icon_name, path=png))
    return groups


def build_sprite_group(group: str, icons: Sequence[IconSpec], out_dir: Path, scale: int) -> None:
    from PIL import Image

    images = []
    for icon in icons:
        img = Image.open(icon.path).convert("RGBA")
        if scale != 1:
            img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
        images.append((icon.name, img))

    padding = 2 * scale
    width = sum(img.width for _, img in images) + padding * (len(images) - 1 if images else 0)
    height = max((img.height for _, img in images), default=1)
    sprite = Image.new("RGBA", (max(width, 1), max(height, 1)), (0, 0, 0, 0))

    manifest = {}
    x = 0
    for name, img in images:
        sprite.paste(img, (x, 0), img)
        manifest[name] = {
            "x": x,
            "y": 0,
            "width": img.width,
            "height": img.height,
            "pixelRatio": scale,
            "sdf": False,
        }
        x += img.width + padding

    suffix = "@2x" if scale == 2 else ""
    png_path = out_dir / f"{group}{suffix}.png"
    json_path = out_dir / f"{group}{suffix}.json"
    sprite.save(png_path)
    json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"built {group}{suffix}: {png_path.name}, {json_path.name} ({len(images)} icons)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sprite PNG/JSON pairs for MapLibre.")
    parser.add_argument("--source", default="assets/sprites", help="Source directory with PNG icons.")
    parser.add_argument("--out", default="dist/assets/sprites", help="Output directory for generated sprite files.")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    groups = discover_groups(source)
    if not groups:
        print(f"no PNG icons found under {source}; nothing to build")
        return 0

    try:
        for group, icons in groups.items():
            build_sprite_group(group, icons, out, scale=1)
            build_sprite_group(group, icons, out, scale=2)
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow is required for sprite building. Install with `pip install Pillow`."
        ) from exc

    print(f"done: generated sprites for {len(groups)} group(s) in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
