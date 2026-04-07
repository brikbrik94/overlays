#!/usr/bin/env python3
import argparse, json, math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
from PIL import Image

@dataclass(frozen=True)
class IconSpec:
    name: str
    path: Path
    sdf: bool = False

def discover_groups(source: Path) -> Dict[str, List[IconSpec]]:
    groups: Dict[str, List[IconSpec]] = {}
    for png in sorted(source.rglob("*.png")):
        # Wir wollen alle Ordner einbeziehen, auch oe5ith-markers
        rel = png.relative_to(source)
        if len(rel.parts) < 2: continue
        group = rel.parts[0]
        icon_name = png.stem
        sdf = icon_name.endswith("-sdf")
        groups.setdefault(group, []).append(IconSpec(name=icon_name, path=png, sdf=sdf))
    return groups

def build_sprite_group(group: str, icons: Sequence[IconSpec], out_dir: Path, scale: int) -> None:
    if not icons: return
    images = []
    for icon in icons:
        img = Image.open(icon.path).convert("RGBA")
        if scale != 1:
            img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
        images.append((icon, img))

    padding = 2 * scale
    total_width = sum(img.width + padding for _, img in images)
    max_height = max(img.height for _, img in images)
    sprite = Image.new("RGBA", (total_width, max_height), (0, 0, 0, 0))
    manifest = {}
    x = 0
    for icon, img in images:
        sprite.paste(img, (x, 0), img)
        entry = {
            "x": x, "y": 0, "width": img.width, "height": img.height,
            "pixelRatio": scale, "sdf": icon.sdf
        }
        if icon.name == "label-bubble-sdf":
            cap = max(1, int(round(img.height * 0.48)))
            inset = max(1, int(round(img.height * 0.22)))
            right_stretch = max(cap + 1, img.width - cap)
            bottom_stretch = max(inset + 1, img.height - inset)
            entry["stretchX"] = [[cap, right_stretch]]
            entry["stretchY"] = [[inset, bottom_stretch]]
            entry["content"] = [inset, inset, max(inset + 1, img.width - inset), max(inset + 1, img.height - inset)]
        manifest[icon.name] = entry
        x += img.width + padding

    group_dir = out_dir / group
    group_dir.mkdir(parents=True, exist_ok=True)
    suffix = "@2x" if scale == 2 else ""
    sprite.save(group_dir / f"sprite{suffix}.png")
    (group_dir / f"sprite{suffix}.json").write_text(json.dumps(manifest, indent=2))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    groups = discover_groups(Path(args.source).resolve())
    for group, icons in groups.items():
        build_sprite_group(group, icons, Path(args.out).resolve(), 1)
        build_sprite_group(group, icons, Path(args.out).resolve(), 2)
        print(f"built {group} ({len(icons)} icons)")

if __name__ == "__main__": main()
