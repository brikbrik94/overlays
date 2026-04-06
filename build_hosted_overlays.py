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
import tempfile
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
ZONEN_COLOR_MAPPING_PATH = REPO_ROOT / "assets" / "mappings" / "color_mapping.json"
DEFAULT_SOURCE_ID = "folder"
DEFAULT_FONT_STACK = ["Segoe UI Regular", "Arial Unicode MS Regular"]
SYMBOL_FOLDERS = {"rd-dienststellen", "nah-stuetzpunkte"}
ICON_BY_FOLDER = {
    "nah-stuetzpunkte": "fallback-pin",
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
    has_zoom_config = any(
        arg in {"-zg", "-z", "-Z", "--maximum-zoom", "--minimum-zoom"}
        for arg in extra_args
    )
    if not has_zoom_config:
        cmd.extend(["-Z", "0", "-z", str(DEFAULT_MAXZOOM)])
    has_drop_strategy = any(
        arg in {"--drop-densest-as-needed", "--drop-fraction-as-needed", "--no-feature-limit", "--no-tile-size-limit"}
        for arg in extra_args
    )
    if not has_drop_strategy:
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
    return ["coalesce", ["get", "pin"], "fallback-pin"]


def build_nah_icon_expression() -> List[Any]:
    return ["coalesce", ["get", "pin"], "fallback-pin"]


def truthy_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "ja"}
    return False


def derive_rd_pin(properties: Dict[str, Any]) -> str:
    emergency = str(properties.get("emergency", "")).strip().lower()
    if emergency == "mountain_rescue":
        return "brd-pin"

    if emergency != "ambulance_station":
        return "fallback-pin"

    has_nef = truthy_value(properties.get("ambulance_station:emergency_doctor"))
    has_rd = truthy_value(properties.get("ambulance_station:patient_transport"))
    if has_nef:
        pin_prefix = "nef"
    elif has_rd or emergency == "ambulance_station":
        # Fallback für Datensätze (z.B. Teile von RD-BY), die
        # `ambulance_station:patient_transport` nicht konsistent pflegen.
        pin_prefix = "rd"
    else:
        return "fallback-pin"

    suffix_by_brand_short = {
        "brk": "brk",
        "örk": "oerk",
        "oerk": "oerk",
        "asb": "asb",
        "mhd": "mhd",
        "juh": "juh",
        "gk": "gk",
        "ma70": "ma70",
        "ims": "ims",
        "stadler": "stadler",
    }
    brand_short = str(properties.get("brand:short", "")).strip().lower()
    suffix = suffix_by_brand_short.get(brand_short)
    if not suffix:
        provider_text = " ".join(
            str(properties.get(key, "")).strip().lower()
            for key in ("brand", "operator", "name", "short_name")
        )
        if "stadler" in provider_text:
            suffix = "stadler"
        elif "malteser" in provider_text:
            suffix = "mhd"
        elif "bayerisches rotes kreuz" in provider_text or " brk" in f" {provider_text} ":
            suffix = "brk"
        elif "österreichisches rotes kreuz" in provider_text or " oerk" in f" {provider_text} " or " örk" in f" {provider_text} ":
            suffix = "oerk"
        elif "samariter" in provider_text or " asb" in f" {provider_text} ":
            suffix = "asb"
        elif "johanniter" in provider_text or " juh" in f" {provider_text} ":
            suffix = "juh"
        elif "grünes kreuz" in provider_text or "gruenes kreuz" in provider_text or " gk" in f" {provider_text} ":
            suffix = "gk"
        elif "ma70" in provider_text or "berufsrettung wien" in provider_text:
            suffix = "ma70"
        elif " ims" in f" {provider_text} ":
            suffix = "ims"
    if not suffix:
        return "fallback-pin"
    return f"{pin_prefix}-{suffix}"


def build_rd_enriched_geojson(src: Path, dst: Path) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    for feature in payload.get("features", []):
        if not isinstance(feature, dict):
            continue
        props = feature.setdefault("properties", {})
        if not isinstance(props, dict):
            props = {}
            feature["properties"] = props
        props["pin"] = derive_rd_pin(props)
    dst.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def derive_nah_pin(properties: Dict[str, Any]) -> str:
    emergency = str(properties.get("emergency", "")).strip().lower()
    if emergency != "air_rescue_service":
        return "fallback-pin"

    provider_text = " ".join(
        str(properties.get(key, "")).strip().lower()
        for key in ("brand", "operator", "name", "short_name", "description", "alt_name")
    )
    provider_text = (
        provider_text.replace("ö", "oe")
        .replace("ä", "ae")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )

    mapping_rules = [
        ("nah-adac-luftrettung", (" adac ", "adac luftrettung")),
        ("nah-drf-luftrettung", (" drf ", "drf luftrettung")),
        ("nah-oeamtc-flugrettung", ("oeamtc", "christophorus flugrettungsverein")),
        ("nah-martin-flugrettung", ("martin flugrettung", "heli austria")),
        ("nah-schenk-air", ("schenkair", "schenk air")),
        ("nah-ara-flugrettung", ("ara luftrettung",)),
        ("nah-wucher-helicopter", ("wucher",)),
        ("nah-shs-schider-helicopter-service", ("schider helicopter service", "shs")),
        ("nah-bundesministerium-des-inneren", ("bundesministerium des inneren", "polizei", "libelle")),
    ]
    text = f" {provider_text} "
    for pin, needles in mapping_rules:
        if any(needle in text for needle in needles):
            return pin
    return "fallback-pin"


def build_nah_enriched_geojson(src: Path, dst: Path) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    for feature in payload.get("features", []):
        if not isinstance(feature, dict):
            continue
        props = feature.setdefault("properties", {})
        if not isinstance(props, dict):
            props = {}
            feature["properties"] = props
        props["pin"] = derive_nah_pin(props)
    dst.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


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
            "icon-size": ["interpolate", ["linear"], ["zoom"], 6, 0.35, 12, 0.65],
            "icon-anchor": "bottom",
            "icon-allow-overlap": True,
            "icon-ignore-placement": True,
            "text-field": ["coalesce", ["get", "alt_name"], ["get", "short_name"], ["get", "name"], ""],
            "text-size": 11,
            "text-font": DEFAULT_FONT_STACK,
            "text-offset": [0, 1.2],
            "text-anchor": "top",
            "text-optional": True,
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
    if bundle.slug == "nah-stuetzpunkte":
        return build_nah_icon_expression()
    return ICON_BY_FOLDER.get(bundle.slug, "fallback-pin")


def build_pmtiles_source_url(base_url: str, pmtiles_relpath: Path) -> str:
    rel = pmtiles_relpath.as_posix()
    if base_url:
        return f"pmtiles://{base_url.rstrip('/')}/{rel}"
    return f"pmtiles://../{rel}"


def build_public_url(base_url: str, relpath: Path) -> str:
    rel = relpath.as_posix()
    if base_url:
        return f"{base_url.rstrip('/')}/{rel}"
    return rel


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

    pmtiles_url = build_pmtiles_source_url(base_url, bundle.pmtiles_relpath)
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
    pmtiles_url = build_pmtiles_source_url(base_url, bundle.pmtiles_relpath)
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
    pmtiles_url = build_pmtiles_source_url(base_url, bundle.pmtiles_relpath)
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


def load_zonen_name_groups() -> Dict[str, int]:
    payload = json.loads(ZONEN_COLOR_MAPPING_PATH.read_text(encoding="utf-8"))
    return {str(name): int(group) for name, group in payload.items()}


def build_zonen_match_expression() -> List[Any]:
    expression: List[Any] = ["match", ["get", "name"]]
    for name, group in sorted(load_zonen_name_groups().items()):
        expression.extend([name, ZONEN_GROUP_COLORS.get(group, ZONEN_FALLBACK_COLOR)])
    expression.append(ZONEN_FALLBACK_COLOR)
    return expression


def apply_zonen_post_processor(style: Dict[str, Any]) -> Dict[str, Any]:
    color_expression = build_zonen_match_expression()
    style.setdefault("metadata", {})["zonenColorFallback"] = ZONEN_FALLBACK_COLOR
    style["metadata"]["zonenColorGroups"] = ZONEN_GROUP_COLORS

    for layer in style.get("layers", []):
        paint = layer.get("paint")
        if not isinstance(paint, dict):
            continue
        if "fill-color" in paint:
            paint["fill-color"] = copy.deepcopy(color_expression)
        if "line-color" in paint:
            paint["line-color"] = copy.deepcopy(color_expression)
        if "circle-color" in paint:
            paint["circle-color"] = copy.deepcopy(color_expression)
    return style


def rewrite_template_style(bundle: BundleSpec, template: Dict[str, Any], base_url: str, sprite_url: Optional[str], glyphs_url: Optional[str]) -> Dict[str, Any]:
    style = copy.deepcopy(template)
    pmtiles_url = build_pmtiles_source_url(base_url, bundle.pmtiles_relpath)

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

    if bundle.slug == "zonen":
        return apply_zonen_post_processor(style)

    return style



def copy_directory_contents(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_static_assets_to_dist(repo_root: Path, out_dir: Path) -> None:
    assets_root = repo_root / "assets"
    copy_directory_contents(assets_root / "mappings", out_dir / "assets" / "mappings")


def clean_output_dir_preserving_sprites(out_dir: Path) -> None:
    if not out_dir.exists():
        return
    preserve_dir = out_dir / "assets" / "sprites"
    for entry in out_dir.iterdir():
        if preserve_dir.exists() and entry.resolve() == preserve_dir.resolve().parent:
            for nested in entry.iterdir():
                if nested.resolve() == preserve_dir.resolve():
                    continue
                if nested.is_dir():
                    shutil.rmtree(nested)
                else:
                    nested.unlink()
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_pmtiles(bundle: BundleSpec, out_dir: Path, extra_args: Sequence[str], dry_run: bool) -> None:
    out_pmtiles = out_dir / bundle.pmtiles_relpath
    out_pmtiles.parent.mkdir(parents=True, exist_ok=True)
    if bundle.slug == "rd-dienststellen":
        with tempfile.TemporaryDirectory(prefix="rd-pin-preprocess-") as temp_dir:
            temp_root = Path(temp_dir)
            enriched_specs: List[LayerSpec] = []
            for spec in bundle.layers:
                enriched_file = temp_root / f"{spec.layer}.geojson"
                build_rd_enriched_geojson(spec.file, enriched_file)
                enriched_specs.append(LayerSpec(layer=spec.layer, file=enriched_file, geom_type=spec.geom_type))
            rd_extra_args = list(extra_args)
            if "--no-feature-limit" not in rd_extra_args:
                rd_extra_args.append("--no-feature-limit")
            if "--no-tile-size-limit" not in rd_extra_args:
                rd_extra_args.append("--no-tile-size-limit")
            has_drop_rate = any(
                arg == "-r" or arg.startswith("-r") or arg == "--drop-rate"
                for arg in rd_extra_args
            )
            if not has_drop_rate:
                rd_extra_args.extend(["-r", "1"])
            cmd = build_tippecanoe_command(out_pmtiles, enriched_specs, rd_extra_args)
            print(f"\n=== {bundle.title} ===")
            print(f"PMTiles: {out_pmtiles}")
            print(">>", " ".join(cmd))
            if not dry_run:
                subprocess.run(cmd, check=True)
        return

    if bundle.slug == "nah-stuetzpunkte":
        with tempfile.TemporaryDirectory(prefix="nah-pin-preprocess-") as temp_dir:
            temp_root = Path(temp_dir)
            enriched_specs: List[LayerSpec] = []
            for spec in bundle.layers:
                enriched_file = temp_root / f"{spec.layer}.geojson"
                build_nah_enriched_geojson(spec.file, enriched_file)
                enriched_specs.append(LayerSpec(layer=spec.layer, file=enriched_file, geom_type=spec.geom_type))
            nah_extra_args = list(extra_args)
            if "--no-feature-limit" not in nah_extra_args:
                nah_extra_args.append("--no-feature-limit")
            if "--no-tile-size-limit" not in nah_extra_args:
                nah_extra_args.append("--no-tile-size-limit")
            has_drop_rate = any(
                arg == "-r" or arg.startswith("-r") or arg == "--drop-rate"
                for arg in nah_extra_args
            )
            if not has_drop_rate:
                nah_extra_args.extend(["-r", "1"])
            cmd = build_tippecanoe_command(out_pmtiles, enriched_specs, nah_extra_args)
            print(f"\n=== {bundle.title} ===")
            print(f"PMTiles: {out_pmtiles}")
            print(">>", " ".join(cmd))
            if not dry_run:
                subprocess.run(cmd, check=True)
        return

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
    parser.add_argument("--base-url", default="", help="Optional public base URL where the bundle will be hosted.")
    parser.add_argument("--sprite-url", default="../assets/sprites/oe5ith-markers/sprite", help="Sprite URL for MapLibre styles.")
    parser.add_argument("--glyphs-url", default="../assets/fonts/{fontstack}/{range}.pbf", help="Glyphs URL for MapLibre styles.")
    parser.add_argument("--skip-pmtiles", action="store_true", help="Do not run tippecanoe, only generate manifests/styles/index.")
    parser.add_argument("--dry-run", action="store_true", help="Print tippecanoe commands without executing them.")
    parser.add_argument("--clean", action="store_true", help="Remove output directory before rebuilding PMTiles/manifests/styles.")
    parser.add_argument("--extra", nargs=argparse.REMAINDER, default=[], help="Extra arguments passed through to tippecanoe.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    if args.clean and out_dir.exists():
        clean_output_dir_preserving_sprites(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    copy_static_assets_to_dist(REPO_ROOT, out_dir)

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
            "styleUrl": build_public_url(args.base_url, bundle.style_relpath),
            "manifestFile": bundle.manifest_relpath.as_posix(),
            "pmtilesFile": bundle.pmtiles_relpath.as_posix(),
            "pmtilesUrl": build_public_url(args.base_url, bundle.pmtiles_relpath),
            "sourceLayerCount": len(bundle.layers),
        })

    write_json(out_dir / "styles" / "index.json", index_entries)
    print(f"\n✅ Fertig: {len(bundles)} Bundles unter {out_dir} erzeugt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
