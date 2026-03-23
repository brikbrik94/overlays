#!/usr/bin/env python3
"""Build a deployable PMTiles + MapLibre style bundle from a GeoJSON folder tree.

The script scans the GeoJSON root for directories that directly contain .geojson files.
Each such directory becomes one deployable overlay bundle consisting of:
- one PMTiles archive (unless --skip-pmtiles is used)
- one manifest JSON
- one MapLibre style JSON
- one global index.json with all bundles

This matches the structure of the existing repo, where folders like
`Straßen/Autobahnen` or `Anfahrtszeit/Linz` should become their own hosted files.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


ACCENT = "#3b82f6"
BACKGROUND = "#1a1a1a"
BORDER = "#333333"
TEXT = "#e0e0e0"
HALO = "#1a1a1a"
DEFAULT_MAXZOOM = 15
TEMPLATE_STYLES_DIR = Path(__file__).resolve().parent / "pmtiles" / "styles"
REPO_ROOT = Path(__file__).resolve().parent
ZONEN_COLOR_MAPPING_PATH = REPO_ROOT / "assets" / "color_mapping.json"
DEFAULT_SOURCE_ID = "folder"
DEFAULT_FONT_STACK = ["Segoe UI Regular", "Arial Unicode MS Regular"]
SYMBOL_FOLDERS = {"rd-dienststellen", "nah-stuetzpunkte"}
ICON_BY_FOLDER = {
    "nah-stuetzpunkte": "nah-pin",
}
ZONEN_FALLBACK_COLOR = "#6b7280"
ANFAHRTSZEIT_COLOR_RAMP = ["#22c55e", "#84cc16", "#eab308", "#f59e0b", "#f97316", "#dc2626"]
LEITSTELLEN_COLOR_PALETTE = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"]


@dataclass(frozen=True)
class LayerSpec:
    layer: str
    file: Path
    geom_type: str


@dataclass(frozen=True)
class BundleSpec:
    relative_dir: Path
    slug: str
    title: str
    pmtiles_relpath: Path
    manifest_relpath: Path
    style_relpath: Path
    layers: List[LayerSpec]


def sanitize_slug(value: str) -> str:
    value = value.lower()
    value = (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    value = value.replace(" ", "-").replace("/", "-").replace("_", "-")
    value = re.sub(r"[^a-z0-9-]", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "bundle"


def sanitize_layer_name(value: str) -> str:
    value = value.lower()
    value = (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    value = value.replace(" ", "_").replace("-", "_")
    value = re.sub(r"[^a-z0-9_]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "layer"


def detect_geom_type_from_geojson(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))

    def classify(kind: str) -> Optional[str]:
        if kind in {"Point", "MultiPoint"}:
            return "point"
        if kind in {"LineString", "MultiLineString"}:
            return "line"
        if kind in {"Polygon", "MultiPolygon"}:
            return "polygon"
        return None

    data_type = data.get("type")
    if data_type == "FeatureCollection":
        for feature in data.get("features") or []:
            geom = (feature or {}).get("geometry") or {}
            detected = classify(geom.get("type", ""))
            if detected:
                return detected
    elif data_type == "Feature":
        geom = data.get("geometry") or {}
        detected = classify(geom.get("type", ""))
        if detected:
            return detected
    elif isinstance(data_type, str):
        detected = classify(data_type)
        if detected:
            return detected

    return "unknown"


def discover_bundle_dirs(root: Path) -> List[Path]:
    bundle_dirs = set()
    for geojson_file in root.rglob("*.geojson"):
        if geojson_file.is_file():
            bundle_dirs.add(geojson_file.parent)
    return sorted(bundle_dirs)


def ensure_unique_layers(layer_specs: Iterable[LayerSpec]) -> List[LayerSpec]:
    seen: Dict[str, int] = {}
    unique: List[LayerSpec] = []
    for item in layer_specs:
        count = seen.get(item.layer, 0) + 1
        seen[item.layer] = count
        if count == 1:
            unique.append(item)
        else:
            unique.append(LayerSpec(layer=f"{item.layer}_{count}", file=item.file, geom_type=item.geom_type))
    return unique


def collect_bundle_spec(root: Path, bundle_dir: Path) -> BundleSpec:
    relative_dir = bundle_dir.relative_to(root)
    layer_specs = []
    for geojson_file in sorted(bundle_dir.glob("*.geojson")):
        layer_specs.append(
            LayerSpec(
                layer=sanitize_layer_name(geojson_file.stem),
                file=geojson_file.resolve(),
                geom_type=detect_geom_type_from_geojson(geojson_file),
            )
        )
    layers = ensure_unique_layers(layer_specs)
    rel_dir_str = relative_dir.as_posix()
    slug = sanitize_slug(rel_dir_str)
    title = rel_dir_str

    pmtiles_relpath = Path("pmtiles") / relative_dir.with_suffix(".pmtiles")
    manifest_relpath = Path("manifests") / relative_dir.with_suffix(".manifest.json")
    style_relpath = Path("styles") / f"{slug}.style.json"

    return BundleSpec(
        relative_dir=relative_dir,
        slug=slug,
        title=title,
        pmtiles_relpath=pmtiles_relpath,
        manifest_relpath=manifest_relpath,
        style_relpath=style_relpath,
        layers=layers,
    )


def build_tippecanoe_command(out_pmtiles: Path, specs: Sequence[LayerSpec], extra_args: Sequence[str]) -> List[str]:
    cmd = ["tippecanoe", "-o", str(out_pmtiles)]
    if "-z" not in extra_args and "-zg" not in extra_args:
        cmd.append("-zg")
    if "--drop-densest-as-needed" not in extra_args and "--drop-fraction-as-needed" not in extra_args:
        cmd.append("--drop-densest-as-needed")
    cmd.extend(extra_args)
    for spec in specs:
        cmd.extend(["-L", f"{spec.layer}:{spec.file}"])
    return cmd


def geometry_filter(*geometry_types: str) -> List[Any]:
    return ["match", ["geometry-type"], list(geometry_types), True, False]


def expr_truthy(prop: str) -> List[Any]:
    return [
        "any",
        ["==", ["get", prop], True],
        ["in", ["downcase", ["to-string", ["get", prop]]], ["literal", ["yes", "true", "1"]]],
    ]


def build_rd_icon_expression() -> List[Any]:
    return [
        "case",
        ["==", ["get", "emergency"], "mountain_rescue"], "brd-pin",
        expr_truthy("ambulance_station:emergency_doctor"), "nef-pin",
        "rd-pin",
    ]


def add_background_layer(style_layers: List[Dict[str, Any]]) -> None:
    style_layers.append({
        "id": "background",
        "type": "background",
        "paint": {"background-color": BACKGROUND},
    })


def add_fill_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str) -> None:
    style_layers.append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "paint": {
            "fill-color": ACCENT,
            "fill-opacity": 0.2,
            "fill-outline-color": BORDER,
        },
    })


def add_line_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str) -> None:
    style_layers.append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("LineString", "MultiLineString", "Polygon", "MultiPolygon"),
        "paint": {
            "line-color": ACCENT,
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.5, 12, 3.5],
            "line-opacity": 0.9,
        },
    })


def add_circle_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str) -> None:
    style_layers.append({
        "id": f"{base_id}-circle",
        "type": "circle",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Point", "MultiPoint"),
        "paint": {
            "circle-color": ACCENT,
            "circle-stroke-color": TEXT,
            "circle-stroke-width": 1,
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 3.5, 12, 6.5],
            "circle-opacity": 0.95,
        },
    })


def add_symbol_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str, icon_image: Any) -> None:
    style_layers.append({
        "id": f"{base_id}-symbols",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Point", "MultiPoint"),
        "layout": {
            "icon-image": icon_image,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 6, 0.5, 12, 0.9],
            "icon-allow-overlap": True,
            "text-field": ["coalesce", ["get", "alt_name"], ["get", "short_name"], ["get", "name"], ""],
            "text-size": 11,
            "text-font": DEFAULT_FONT_STACK,
            "text-offset": [0, 1.2],
            "text-anchor": "top",
        },
        "paint": {
            "text-color": TEXT,
            "text-halo-color": HALO,
            "text-halo-width": 1,
        },
    })


def should_use_symbol_points(bundle: BundleSpec) -> bool:
    return bundle.slug in SYMBOL_FOLDERS


def point_icon_for_bundle(bundle: BundleSpec) -> Any:
    if bundle.slug == "rd-dienststellen":
        return build_rd_icon_expression()
    return ICON_BY_FOLDER.get(bundle.slug, "fallback-pin")


def build_style(bundle: BundleSpec, base_url: str, sprite_url: Optional[str], glyphs_url: Optional[str]) -> Dict[str, Any]:
    if bundle.slug == "zonen":
        return build_zonen_style(bundle, base_url, sprite_url, glyphs_url)
    if bundle.slug == "anfahrtszeit-linz":
        return build_anfahrtszeit_style(bundle, base_url, sprite_url, glyphs_url)
    if bundle.slug == "leitstellen-bereiche":
        return build_leitstellen_bereiche_style(bundle, base_url, sprite_url, glyphs_url)

    template = load_template_style(bundle)
    if template is not None:
        return rewrite_template_style(bundle, template, base_url, sprite_url, glyphs_url)

    pmtiles_url = f"pmtiles://{base_url.rstrip('/')}/{bundle.pmtiles_relpath.as_posix()}"
    style: Dict[str, Any] = {
        "version": 8,
        "name": f"OE5ITH {bundle.title} (CI)",
        "metadata": {
            "generator": "build_hosted_overlays.py",
            "folder": bundle.title,
            "sourceLayers": [layer.layer for layer in bundle.layers],
            "ci": {
                "topbarHeight": 60,
                "accent": ACCENT,
            },
        },
        "sources": {
            DEFAULT_SOURCE_ID: {
                "type": "vector",
                "url": pmtiles_url,
                "minzoom": 0,
                "maxzoom": DEFAULT_MAXZOOM,
            }
        },
        "layers": [],
    }
    if glyphs_url:
        style["glyphs"] = glyphs_url
    if sprite_url:
        style["sprite"] = sprite_url

    layers = style["layers"]
    add_background_layer(layers)

    use_symbol_points = should_use_symbol_points(bundle)
    point_icon = point_icon_for_bundle(bundle)

    for spec in bundle.layers:
        base_id = f"{bundle.slug}-{spec.layer}"
        add_fill_layer(layers, base_id, spec.layer)
        add_line_layer(layers, base_id, spec.layer)
        if use_symbol_points:
            add_symbol_layer(layers, base_id, spec.layer, point_icon)
        else:
            add_circle_layer(layers, base_id, spec.layer)

    return style



def zonen_feature_key(properties: Dict[str, Any]) -> Optional[str]:
    value = properties.get("alt_name") or properties.get("name")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_zonen_color_mapping() -> Dict[str, str]:
    payload = json.loads(ZONEN_COLOR_MAPPING_PATH.read_text(encoding="utf-8"))
    return {str(name): str(color) for name, color in payload.items()}


def zonen_layer_keys(layer_spec: LayerSpec) -> List[str]:
    data = json.loads(layer_spec.file.read_text(encoding="utf-8"))
    keys: List[str] = []
    seen = set()
    for feature in data.get("features", []):
        properties = (feature or {}).get("properties") or {}
        key = zonen_feature_key(properties)
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def build_zonen_layer_match_expression(layer_spec: LayerSpec, color_mapping: Dict[str, str]) -> List[Any]:
    expression: List[Any] = ["match", ["coalesce", ["get", "alt_name"], ["get", "name"]]]
    for key in zonen_layer_keys(layer_spec):
        color = color_mapping.get(key)
        if color:
            expression.extend([key, color])
    expression.append(ZONEN_FALLBACK_COLOR)
    return expression


def add_zonen_fill_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str, color_expression: List[Any]) -> None:
    style_layers.append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "paint": {
            "fill-color": copy.deepcopy(color_expression),
            "fill-opacity": 0.2,
            "fill-outline-color": BORDER,
        },
    })


def add_zonen_line_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str, color_expression: List[Any]) -> None:
    style_layers.append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "paint": {
            "line-color": copy.deepcopy(color_expression),
            "line-width": 2,
            "line-opacity": 0.9,
        },
    })


def build_zonen_style(bundle: BundleSpec, base_url: str, sprite_url: Optional[str], glyphs_url: Optional[str]) -> Dict[str, Any]:
    pmtiles_url = f"pmtiles://{base_url.rstrip('/')}/{bundle.pmtiles_relpath.as_posix()}"
    color_mapping = load_zonen_color_mapping()
    style: Dict[str, Any] = {
        "version": 8,
        "name": f"OE5ITH {bundle.title} (CI)",
        "metadata": {
            "generator": "build_hosted_overlays.py",
            "folder": bundle.title,
            "sourceLayers": [layer.layer for layer in bundle.layers],
            "zonenColorSource": ZONEN_COLOR_MAPPING_PATH.relative_to(REPO_ROOT).as_posix(),
            "zonenColorFallback": ZONEN_FALLBACK_COLOR,
        },
        "sources": {
            DEFAULT_SOURCE_ID: {
                "type": "vector",
                "url": pmtiles_url,
                "minzoom": 0,
                "maxzoom": DEFAULT_MAXZOOM,
            }
        },
        "layers": [],
    }
    if glyphs_url:
        style["glyphs"] = glyphs_url
    if sprite_url:
        style["sprite"] = sprite_url

    layers = style["layers"]
    add_background_layer(layers)
    for spec in bundle.layers:
        color_expression = build_zonen_layer_match_expression(spec, color_mapping)
        base_id = f"{bundle.slug}-{spec.layer}"
        add_zonen_fill_layer(layers, base_id, spec.layer, color_expression)
        add_zonen_line_layer(layers, base_id, spec.layer, color_expression)

    return style



def add_constant_fill_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str, color: str) -> None:
    style_layers.append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "paint": {
            "fill-color": color,
            "fill-opacity": 0.2,
            "fill-outline-color": BORDER,
        },
    })


def add_constant_line_layer(style_layers: List[Dict[str, Any]], base_id: str, source_layer: str, color: str) -> None:
    style_layers.append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "paint": {
            "line-color": color,
            "line-width": 2,
            "line-opacity": 0.9,
        },
    })


def build_polygon_bundle_style(
    bundle: BundleSpec,
    base_url: str,
    sprite_url: Optional[str],
    glyphs_url: Optional[str],
    color_by_layer: Dict[str, str],
    metadata_extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pmtiles_url = f"pmtiles://{base_url.rstrip('/')}/{bundle.pmtiles_relpath.as_posix()}"
    metadata: Dict[str, Any] = {
        "generator": "build_hosted_overlays.py",
        "folder": bundle.title,
        "sourceLayers": [layer.layer for layer in bundle.layers],
    }
    if metadata_extra:
        metadata.update(metadata_extra)

    style: Dict[str, Any] = {
        "version": 8,
        "name": f"OE5ITH {bundle.title} (CI)",
        "metadata": metadata,
        "sources": {
            DEFAULT_SOURCE_ID: {
                "type": "vector",
                "url": pmtiles_url,
                "minzoom": 0,
                "maxzoom": DEFAULT_MAXZOOM,
            }
        },
        "layers": [],
    }
    if glyphs_url:
        style["glyphs"] = glyphs_url
    if sprite_url:
        style["sprite"] = sprite_url

    layers = style["layers"]
    add_background_layer(layers)
    for spec in bundle.layers:
        color = color_by_layer.get(spec.layer, ACCENT)
        base_id = f"{bundle.slug}-{spec.layer}"
        add_constant_fill_layer(layers, base_id, spec.layer, color)
        add_constant_line_layer(layers, base_id, spec.layer, color)
    return style


def anfahrtszeit_sort_key(layer_name: str) -> tuple[int, int]:
    parts = [int(part) for part in re.findall(r"\d+", layer_name)]
    if len(parts) >= 2:
        return (max(parts[0], parts[1]), min(parts[0], parts[1]))
    if parts:
        return (parts[0], parts[0])
    return (10**9, 10**9)


def pick_palette_color(palette: Sequence[str], index: int, total: int) -> str:
    if total <= 1:
        return palette[0]
    if total <= len(palette):
        palette_index = round(index * (len(palette) - 1) / (total - 1))
        return palette[palette_index]
    return palette[index % len(palette)]


def build_anfahrtszeit_style(bundle: BundleSpec, base_url: str, sprite_url: Optional[str], glyphs_url: Optional[str]) -> Dict[str, Any]:
    ordered_layers = sorted(bundle.layers, key=lambda spec: anfahrtszeit_sort_key(spec.layer))
    color_by_layer = {
        spec.layer: pick_palette_color(ANFAHRTSZEIT_COLOR_RAMP, index, len(ordered_layers))
        for index, spec in enumerate(ordered_layers)
    }
    return build_polygon_bundle_style(
        bundle,
        base_url,
        sprite_url,
        glyphs_url,
        color_by_layer,
        metadata_extra={"colorStrategy": "travel-time-ramp"},
    )


def build_leitstellen_bereiche_style(bundle: BundleSpec, base_url: str, sprite_url: Optional[str], glyphs_url: Optional[str]) -> Dict[str, Any]:
    color_by_layer = {
        spec.layer: pick_palette_color(LEITSTELLEN_COLOR_PALETTE, index, len(bundle.layers))
        for index, spec in enumerate(bundle.layers)
    }
    return build_polygon_bundle_style(
        bundle,
        base_url,
        sprite_url,
        glyphs_url,
        color_by_layer,
        metadata_extra={"colorStrategy": "source-layer-palette"},
    )



def template_style_path(bundle: BundleSpec) -> Path:
    return TEMPLATE_STYLES_DIR / f"{bundle.slug}.style.json"


def load_template_style(bundle: BundleSpec) -> Optional[Dict[str, Any]]:
    candidate = template_style_path(bundle)
    if not candidate.exists():
        return None
    return json.loads(candidate.read_text(encoding="utf-8"))


def rewrite_template_style(bundle: BundleSpec, template: Dict[str, Any], base_url: str, sprite_url: Optional[str], glyphs_url: Optional[str]) -> Dict[str, Any]:
    style = copy.deepcopy(template)
    pmtiles_url = f"pmtiles://{base_url.rstrip('/')}/{bundle.pmtiles_relpath.as_posix()}"

    style["name"] = template.get("name") or f"OE5ITH {bundle.title} (CI)"
    style.setdefault("metadata", {})["generator"] = "build_hosted_overlays.py"
    style.setdefault("metadata", {})["folder"] = bundle.title
    style.setdefault("metadata", {})["sourceLayers"] = [layer.layer for layer in bundle.layers]

    for source in style.get("sources", {}).values():
        if source.get("type") == "vector":
            source["url"] = pmtiles_url
            source.setdefault("minzoom", 0)
            source.setdefault("maxzoom", DEFAULT_MAXZOOM)

    if glyphs_url:
        style["glyphs"] = glyphs_url
    if sprite_url:
        style["sprite"] = sprite_url

    return style

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_pmtiles(bundle: BundleSpec, out_dir: Path, extra_args: Sequence[str], dry_run: bool) -> None:
    out_pmtiles = out_dir / bundle.pmtiles_relpath
    out_pmtiles.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_tippecanoe_command(out_pmtiles, bundle.layers, extra_args)
    print(f"\n=== {bundle.title} ===")
    print(f"PMTiles: {out_pmtiles}")
    print(">>", " ".join(cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deployable PMTiles + styles from a GeoJSON folder tree.")
    parser.add_argument("--root", default="geojson", help="GeoJSON root directory.")
    parser.add_argument("--out", default="dist", help="Output directory for hosted bundle.")
    parser.add_argument("--base-url", default="https://tiles.oe5ith.at", help="Public base URL where the bundle will be hosted.")
    parser.add_argument("--sprite-url", default="https://tiles.oe5ith.at/assets/sprites/oe5ith-markers", help="Sprite base URL for MapLibre styles.")
    parser.add_argument("--glyphs-url", default="https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf", help="Glyphs URL for MapLibre styles.")
    parser.add_argument("--skip-pmtiles", action="store_true", help="Do not run tippecanoe, only generate manifests/styles/index.")
    parser.add_argument("--dry-run", action="store_true", help="Print tippecanoe commands without executing them.")
    parser.add_argument("--extra", nargs=argparse.REMAINDER, default=[], help="Extra arguments passed through to tippecanoe.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_dirs = discover_bundle_dirs(root)
    if not bundle_dirs:
        raise SystemExit(f"Keine GeoJSON-Dateien unter {root} gefunden.")

    bundles = [collect_bundle_spec(root, bundle_dir) for bundle_dir in bundle_dirs]

    if not args.skip_pmtiles and not args.dry_run and shutil.which("tippecanoe") is None:
        raise SystemExit("tippecanoe nicht gefunden. Nutze --skip-pmtiles oder installiere tippecanoe.")

    index_entries = []
    for bundle in bundles:
        manifest_payload = {
            "root": str(root),
            "folder": bundle.title,
            "pmtiles": str(out_dir / bundle.pmtiles_relpath),
            "layers": [{"layer": layer.layer, "file": str(layer.file), "geom_type": layer.geom_type} for layer in bundle.layers],
        }
        write_json(out_dir / bundle.manifest_relpath, manifest_payload)

        style_payload = build_style(bundle, args.base_url, args.sprite_url, args.glyphs_url)
        write_json(out_dir / bundle.style_relpath, style_payload)

        if not args.skip_pmtiles:
            build_pmtiles(bundle, out_dir, args.extra, args.dry_run)

        index_entries.append({
            "folder": bundle.title,
            "styleFile": bundle.style_relpath.as_posix(),
            "styleUrl": f"{args.base_url.rstrip('/')}/{bundle.style_relpath.as_posix()}",
            "manifestFile": bundle.manifest_relpath.as_posix(),
            "pmtilesFile": bundle.pmtiles_relpath.as_posix(),
            "pmtilesUrl": f"{args.base_url.rstrip('/')}/{bundle.pmtiles_relpath.as_posix()}",
            "sourceLayerCount": len(bundle.layers),
        })

    write_json(out_dir / "styles" / "index.json", index_entries)
    print(f"\n✅ Fertig: {len(bundles)} Bundles unter {out_dir} erzeugt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
