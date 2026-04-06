#!/usr/bin/env python3
"""
generate_style_from_manifest_v3.py

Generates a MapLibre style.json that:
- contains ALL source-layer names from a PMTiles build manifest
- applies line styling based on linien.json using properties.LINIE
- applies polygon color styling based on color_mapping.json using properties.name
- can emit a report to validate that:
   - all LINIE values seen in line GeoJSONs exist in linien.json
   - all name values seen in polygon GeoJSONs exist in color_mapping.json

Notes:
- MapLibre expressions require a syntactic fallback. We set fallbacks to values
  that effectively render nothing (e.g., line-width 0.0), and use the report to
  detect missing mappings.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def sanitize_id(s: str) -> str:
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


def load_json(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    return json.loads(p.read_text(encoding="utf-8"))


def detect_geom_type_from_geojson(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    def classify(t: str) -> Optional[str]:
        if t in ("Point", "MultiPoint"):
            return "point"
        if t in ("LineString", "MultiLineString"):
            return "line"
        if t in ("Polygon", "MultiPolygon"):
            return "polygon"
        return None

    t = data.get("type")
    if t == "FeatureCollection":
        feats = data.get("features") or []
        for f in feats[:50]:
            g = (f or {}).get("geometry") or {}
            k = classify(g.get("type", ""))
            if k:
                return k
        return None
    if t == "Feature":
        g = (data.get("geometry") or {})
        return classify(g.get("type", ""))
    if isinstance(t, str):
        return classify(t)
    return None


def iter_feature_properties(path: Path, sample_limit: int = 0) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    t = data.get("type")
    props: List[dict] = []

    if t == "FeatureCollection":
        feats = data.get("features") or []
        if sample_limit > 0:
            feats = feats[:sample_limit]
        for f in feats:
            props.append((f or {}).get("properties") or {})
        return props

    if t == "Feature":
        props.append(data.get("properties") or {})
        return props

    return props


# ----------------------------
# MapLibre expressions helpers
# ----------------------------

def expr_truthy(prop: str) -> list:
    return [
        "any",
        ["==", ["get", prop], True],
        ["in", ["downcase", ["to-string", ["get", prop]]], ["literal", ["yes", "true", "1"]]],
    ]


def build_icon_case_expression(sprite_ids: Dict[str, str]) -> list:
    nef = sprite_ids.get("nef", "fallback-pin")
    nah = sprite_ids.get("nah", "fallback-pin")
    brd = sprite_ids.get("brd", "brd-pin")
    rd  = sprite_ids.get("rd",  "fallback-pin")
    fb  = sprite_ids.get("fallback", "fallback-pin")

    return [
        "case",
        expr_truthy("ambulance_station:emergency_doctor"), nef,
        ["in", "aeromedical", ["downcase", ["to-string", ["get", "air_rescue_service"]]]], nah,
        ["==", ["get", "emergency"], "mountain_rescue"], brd,
        ["==", ["get", "emergency"], "ambulance_station"], rd,
        fb,
    ]


def build_line_match_expressions(linien_json: dict) -> Tuple[list, list, list]:
    styles_by_type = (linien_json or {}).get("stylesByType", {})
    linien = (linien_json or {}).get("linien", {})

    # Your cleaned GeoJSONs provide properties.LINIE directly.
    line_key = ["to-string", ["get", "LINIE"]]

    color_match = ["match", line_key]
    width_match = ["match", line_key]
    offset_match = ["match", line_key]

    for lid, spec in linien.items():
        c = spec.get("color")
        t = spec.get("type")
        off = spec.get("offset", 0)
        w = (styles_by_type.get(t, {}) or {}).get("strokeWidth", 2)

        if c:
            color_match.extend([str(lid), c])
        width_match.extend([str(lid), float(w)])
        offset_match.extend([str(lid), float(off)])

    # syntactic fallback: render nothing
    color_match.append("#000000")
    width_match.append(0.0)
    offset_match.append(0.0)

    return color_match, width_match, offset_match


def build_color_mapping_expression(color_mapping: dict,
                                  palette: Dict[str, str],
                                  key_prop: str = "name") -> list:
    key_expr = ["to-string", ["get", key_prop]]
    match_expr = ["match", key_expr]

    for k, idx in (color_mapping or {}).items():
        col = palette.get(str(idx))
        if not col:
            continue
        match_expr.extend([str(k), col])

    # syntactic fallback; opacity controls visibility
    match_expr.append("#000000")
    return match_expr


# ----------------------------
# MapLibre layer builders
# ----------------------------

def add_polygon(style_layers: list, src: str, base_id: str, src_layer: str, fill_color: Any) -> None:
    style_layers.append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": src,
        "source-layer": src_layer,
        "paint": {
            "fill-color": fill_color,
            "fill-opacity": 0.5
        }
    })
    style_layers.append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": src,
        "source-layer": src_layer,
        "paint": {
            "line-color": fill_color,
            "line-width": 1.2
        }
    })


def add_line(style_layers: list, src: str, base_id: str, src_layer: str,
             line_color: Any, line_width: Any, line_offset: Any) -> None:
    style_layers.append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": src,
        "source-layer": src_layer,
        "paint": {
            "line-color": line_color,
            "line-width": line_width,
            "line-offset": line_offset
        }
    })


def add_points(style_layers: list, src: str, base_id: str, src_layer: str,
               icon_expr: Any, use_sprites: bool) -> None:
    if use_sprites:
        style_layers.append({
            "id": f"{base_id}-points",
            "type": "symbol",
            "source": src,
            "source-layer": src_layer,
            "layout": {
                "icon-image": icon_expr,
                "icon-size": 1.0,
                "icon-anchor": "bottom",
                "icon-allow-overlap": True
            }
        })
    else:
        style_layers.append({
            "id": f"{base_id}-points",
            "type": "circle",
            "source": src,
            "source-layer": src_layer,
            "paint": {
                "circle-radius": 4,
                "circle-color": "#ff00ff",
                "circle-opacity": 0.9
            }
        })


# ----------------------------
# Reporting
# ----------------------------

def build_report(manifest_layers: list,
                 linien_json: dict,
                 color_mapping: dict,
                 name_prop: str,
                 sample_limit: int) -> dict:
    known_linien = set((linien_json or {}).get("linien", {}).keys())
    known_names = set(color_mapping.keys())

    seen_linien = Counter()
    seen_names = Counter()

    for item in manifest_layers:
        fpath = Path(item["file"])
        geom = detect_geom_type_from_geojson(fpath) or "point"
        props_list = iter_feature_properties(fpath, sample_limit=sample_limit)

        if geom == "line":
            for p in props_list:
                v = p.get("LINIE")
                if v is not None:
                    seen_linien[str(v)] += 1
        elif geom == "polygon":
            for p in props_list:
                v = p.get(name_prop)
                if v is not None:
                    seen_names[str(v)] += 1

    missing_linien = sorted([k for k in seen_linien.keys() if k not in known_linien])
    missing_names = sorted([k for k in seen_names.keys() if k not in known_names])

    return {
        "scanned": {
            "files": len(manifest_layers),
            "sample_limit_per_file": sample_limit
        },
        "linien": {
            "known_in_linien_json": len(known_linien),
            "seen_in_geojson": len(seen_linien),
            "missing_ids": missing_linien,
            "top_seen": seen_linien.most_common(25),
        },
        "color_mapping": {
            "name_prop": name_prop,
            "known_in_color_mapping_json": len(known_names),
            "seen_in_geojson": len(seen_names),
            "missing_names": missing_names,
            "top_seen": seen_names.most_common(25),
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="*.manifest.json aus dem PMTiles-Build")
    ap.add_argument("--pmtiles-url", required=True, help='pmtiles://https://.../thema.pmtiles')
    ap.add_argument("--out-style", required=True, help="Output style.json")
    ap.add_argument("--name", default="Generated Style")
    ap.add_argument("--source-id", default="thema")
    ap.add_argument("--sprite", default=None)
    ap.add_argument("--glyphs", default=None)

    ap.add_argument("--linien-json", required=True, help="linien.json")
    ap.add_argument("--color-mapping", required=True, help="color_mapping.json")

    ap.add_argument("--palette-json", default=None,
                    help="Optional: JSON dict or list for index->color. If omitted: default palette is used.")
    ap.add_argument("--use-sprites", action="store_true")

    ap.add_argument("--name-prop", default="name", help="Property for color_mapping lookup (default: name)")
    ap.add_argument("--report", default=None, help="Optional: write report JSON")
    ap.add_argument("--report-sample-limit", type=int, default=0,
                    help="0=scan all features; >0=scan at most N features per file (faster).")

    args = ap.parse_args()

    manifest = load_json(args.manifest)
    manifest_layers = manifest.get("layers") or []
    if not manifest_layers:
        raise SystemExit("Manifest hat keine layers[]")

    linien_json = load_json(args.linien_json)
    color_mapping = load_json(args.color_mapping)

    # Default palette placeholder; replace with your real palette if needed
    palette = {
        "1": "#e41a1c",
        "2": "#377eb8",
        "3": "#4daf4a",
        "4": "#984ea3",
        "5": "#ff7f00",
        "6": "#ffff33",
    }

    if args.palette_json:
        pj = load_json(args.palette_json)
        if isinstance(pj, list):
            palette = {str(i + 1): v for i, v in enumerate(pj)}
        elif isinstance(pj, dict):
            palette = {str(k): v for k, v in pj.items()}

    icon_expr = build_icon_case_expression({
        "rd": "fallback-pin",
        "nef": "fallback-pin",
        "nah": "fallback-pin",
        "brd": "brd-pin",
        "fallback": "fallback-pin"
    })
    line_color_expr, line_width_expr, line_offset_expr = build_line_match_expressions(linien_json)
    fill_color_expr = build_color_mapping_expression(color_mapping, palette, key_prop=args.name_prop)

    style: Dict[str, Any] = {
        "version": 8,
        "name": args.name,
        "sources": {
            args.source_id: {"type": "vector", "url": args.pmtiles_url}
        },
        "layers": []
    }
    if args.sprite:
        style["sprite"] = args.sprite
    if args.glyphs:
        style["glyphs"] = args.glyphs

    out_layers: List[Dict[str, Any]] = []
    for item in manifest_layers:
        src_layer = item["layer"]
        geojson_path = Path(item["file"])
        base_id = sanitize_id(src_layer)

        geom = detect_geom_type_from_geojson(geojson_path) or "point"
        if geom == "polygon":
            add_polygon(out_layers, args.source_id, base_id, src_layer, fill_color_expr)
        elif geom == "line":
            add_line(out_layers, args.source_id, base_id, src_layer,
                     line_color_expr, line_width_expr, line_offset_expr)
        else:
            add_points(out_layers, args.source_id, base_id, src_layer, icon_expr, args.use_sprites)

    style["layers"] = out_layers

    out_path = Path(args.out_style).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(style, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ style.json geschrieben: {out_path} ({len(out_layers)} MapLibre-Layer)")

    if args.report:
        report = build_report(
            manifest_layers=manifest_layers,
            linien_json=linien_json,
            color_mapping=color_mapping,
            name_prop=args.name_prop,
            sample_limit=args.report_sample_limit
        )
        rpath = Path(args.report).expanduser().resolve()
        rpath.parent.mkdir(parents=True, exist_ok=True)
        rpath.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"📄 Report geschrieben: {rpath}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
