#!/usr/bin/env python3
"""
geojson_to_pmtiles.py

Build PMTiles from many GeoJSON files using tippecanoe.

Modes:
1) Single PMTiles (default):
   - scans --root recursively for *.geojson
   - each file becomes one vector source-layer inside one PMTiles output (--out)

2) Split per top-level folder (--split-top-folders):
   - builds one PMTiles per first-level folder under --root
   - each file inside that folder becomes one source-layer in that PMTiles
   - --out must be an OUTPUT DIRECTORY in this mode

Additionally:
- --write-manifest writes a build manifest JSON that lists source-layer -> file.
  The manifest is intended to be used by the style generator.

Requirements:
- tippecanoe must be installed and available in PATH.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class LayerSpec:
    layer: str
    file: Path


def sanitize_layer_name(s: str) -> str:
    s = s.lower()
    s = (
        s.replace("ä", "ae")
         .replace("ö", "oe")
         .replace("ü", "ue")
         .replace("ß", "ss")
    )
    s = s.replace(" ", "_").replace("-", "_")
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "layer"


def find_geojson_files(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob("*.geojson") if p.is_file())


def ensure_unique_layers(specs: List[LayerSpec]) -> List[LayerSpec]:
    seen: Dict[str, int] = {}
    out: List[LayerSpec] = []
    for s in specs:
        n = seen.get(s.layer, 0) + 1
        seen[s.layer] = n
        if n == 1:
            out.append(s)
        else:
            out.append(LayerSpec(layer=f"{s.layer}_{n}", file=s.file))
    return out


def check_tippecanoe_available() -> None:
    if shutil.which("tippecanoe") is None:
        raise RuntimeError("tippecanoe nicht gefunden (nicht im PATH).")


def build_tippecanoe_command(out_pmtiles: Path, specs: List[LayerSpec], extra_args: List[str]) -> List[str]:
    cmd = ["tippecanoe", "-o", str(out_pmtiles)]

    # sensible defaults unless user overrides via --extra
    if "-z" not in extra_args and "-zg" not in extra_args:
        cmd.append("-zg")
    if "--drop-densest-as-needed" not in extra_args and "--drop-fraction-as-needed" not in extra_args:
        cmd.append("--drop-densest-as-needed")

    cmd.extend(extra_args)

    # each file becomes one source-layer via -L layer:file
    for s in specs:
        cmd.extend(["-L", f"{s.layer}:{s.file}"])

    return cmd


def run(cmd: List[str]) -> int:
    print(">>", " ".join(cmd))
    return subprocess.run(cmd).returncode


def build_layer_name(root: Path, file_path: Path, theme_prefix: Optional[str], top_folder_mode: bool) -> str:
    """
    - default (single mode): layername from relative path incl. top-level folder
    - split-top-folders mode: layername from relative path WITHOUT the top-level folder
      so inside e.g. 'strassen.pmtiles' you get 'autobahnen_a1' etc.
    """
    rel = file_path.relative_to(root)
    parts = list(rel.parts)

    if top_folder_mode and len(parts) > 1:
        parts = parts[1:]

    # drop extension
    if parts[-1].lower().endswith(".geojson"):
        parts[-1] = Path(parts[-1]).stem

    base = sanitize_layer_name("_".join(parts))
    if theme_prefix:
        return f"{sanitize_layer_name(theme_prefix)}__{base}"
    return base


def group_by_top_folder(root: Path, files: List[Path]) -> Dict[str, List[Path]]:
    groups: Dict[str, List[Path]] = {}
    for f in files:
        rel = f.relative_to(root)
        top = rel.parts[0] if rel.parts else "_root"
        groups.setdefault(top, []).append(f)
    return groups


def main() -> int:
    ap = argparse.ArgumentParser(description="Build PMTiles from many GeoJSON files (each file -> source-layer).")
    ap.add_argument("--root", required=True, help="Root-Ordner mit GeoJSON-Struktur")
    ap.add_argument("--out", required=True,
                    help="Output PMTiles Pfad (single mode) ODER Output-Ordner (--split-top-folders).")
    ap.add_argument("--theme", default=None, help="Optional: Prefix für Layernamen (single mode).")
    ap.add_argument("--write-manifest", default=None,
                    help="Manifest JSON (single mode: Datei / split mode: Ordner).")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, tippecanoe nicht ausführen")
    ap.add_argument("--split-top-folders", action="store_true",
                    help="Erzeuge pro Top-Level-Ordner eine eigene PMTiles.")
    ap.add_argument("--extra", nargs=argparse.REMAINDER, default=[],
                    help="Alles nach --extra wird 1:1 an tippecanoe durchgereicht, z.B. --extra -z 14")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    files = find_geojson_files(root)
    if not files:
        print("Keine .geojson Dateien gefunden.")
        return 2

    if args.split_top_folders:
        out_dir = Path(args.out).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        manifest_dir: Optional[Path] = None
        if args.write_manifest:
            manifest_dir = Path(args.write_manifest).expanduser().resolve()
            manifest_dir.mkdir(parents=True, exist_ok=True)

        groups = group_by_top_folder(root, files)

        if not args.dry_run:
            check_tippecanoe_available()

        for top, gfiles in sorted(groups.items(), key=lambda kv: kv[0].lower()):
            out_pmtiles = out_dir / f"{sanitize_layer_name(top)}.pmtiles"

            specs = [LayerSpec(
                layer=build_layer_name(root, f, theme_prefix=None, top_folder_mode=True),
                file=f
            ) for f in gfiles]
            specs = ensure_unique_layers(specs)

            print(f"\n=== {top} ===")
            print(f"  files : {len(specs)}")
            print(f"  out   : {out_pmtiles}")

            if manifest_dir:
                m = {
                    "root": str(root),
                    "group": top,
                    "out": str(out_pmtiles),
                    "count": len(specs),
                    "layers": [{"layer": s.layer, "file": str(s.file)} for s in specs],
                }
                (manifest_dir / f"{sanitize_layer_name(top)}.manifest.json").write_text(
                    json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8"
                )

            cmd = build_tippecanoe_command(out_pmtiles, specs, args.extra)
            if args.dry_run:
                print("  dry-run (no build)")
                print("  cmd:", " ".join(cmd[:10] + ["..."]))
            else:
                rc = run(cmd)
                if rc != 0:
                    print(f"tippecanoe failed for group '{top}' (exit {rc})")
                    return rc

        print("\n✅ Fertig: Split-Build abgeschlossen.")
        return 0

    # Single PMTiles mode
    out_pmtiles = Path(args.out).expanduser().resolve()
    out_pmtiles.parent.mkdir(parents=True, exist_ok=True)

    specs = [LayerSpec(layer=build_layer_name(root, f, args.theme, top_folder_mode=False), file=f) for f in files]
    specs = ensure_unique_layers(specs)

    if args.write_manifest:
        manifest_path = Path(args.write_manifest).expanduser().resolve()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "root": str(root),
            "out": str(out_pmtiles),
            "theme": args.theme,
            "count": len(specs),
            "layers": [{"layer": s.layer, "file": str(s.file)} for s in specs],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Root: {root}")
    print(f"Out : {out_pmtiles}")
    print(f"Files/Layer: {len(specs)}")

    if args.dry_run:
        print("Dry-run: kein Build.")
        return 0

    check_tippecanoe_available()
    cmd = build_tippecanoe_command(out_pmtiles, specs, args.extra)
    rc = run(cmd)
    if rc != 0:
        print(f"tippecanoe exit code: {rc}")
        return rc

    print(f"✅ Fertig: {out_pmtiles}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
