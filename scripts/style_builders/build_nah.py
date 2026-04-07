#!/usr/bin/env python3
import argparse, os, json, re
from pathlib import Path
from style_utils import create_base_style, build_pmtiles_source_url, write_style, geometry_filter, DEFAULT_SOURCE_ID, DEFAULT_FONT_STACK

def get_layer_type(manifest, layer_name, folder_rel):
    """Ermittelt den Typ (Point oder Polygon) aus dem Manifest."""
    search_name = f"{folder_rel}/{layer_name}.geojson"
    for item in manifest.get("files", []):
        if item.get("name") == search_name:
            types = item.get("feature_types", [])
            if "Point" in types:
                return "point"
            if "Polygon" in types or "MultiPolygon" in types:
                return "polygon"
    return "unknown"

def add_nah_point_layer(style, source_layer):
    base_id = f"nah-{source_layer}"
    
    # Symbol Layer (Pins)
    style["layers"].append({
        "id": f"{base_id}-symbols",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Point"),
        "layout": {
            "icon-image": ["coalesce", ["get", "pin"], "fallback-pin"],
            "icon-size": ["interpolate", ["linear"], ["zoom"], 6, 0.35, 12, 0.65],
            "icon-anchor": "bottom",
            "icon-allow-overlap": True
        }
    })
    
    # Text Layer (SDF Bubble, feld 'alt_name' unter dem Pin)
    style["layers"].append({
        "id": f"{base_id}-text",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": ["all",
            geometry_filter("Point"),
            ["has", "alt_name"],
            ["!=", ["get", "alt_name"], ""]
        ],
        "layout": {
            "text-field": ["get", "alt_name"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 6, 9.5, 12, 11],
            "text-font": DEFAULT_FONT_STACK,
            "text-variable-anchor": ["top"],
            "text-radial-offset": 1.5,
            "text-allow-overlap": True,
            "text-ignore-placement": True,
            "text-optional": False,
            "icon-image": "label-bubble",
            "icon-anchor": "top",
            "icon-text-fit": "both",
            "icon-text-fit-padding": [1, 3, 1, 3],
            "icon-allow-overlap": True,
            "icon-ignore-placement": True,
            "icon-optional": True
        },
        "paint": {
            "text-color": "#111827",
            "icon-opacity": 0.95
        }
    })

def add_nah_polygon_layer(style, source_layer):
    base_id = f"nah-{source_layer}"
    
    # Fill Layer
    style["layers"].append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "paint": {
            "fill-color": "#3b82f6",
            "fill-opacity": 0.15,
            "fill-outline-color": "#3b82f6"
        }
    })
    
    # Line Layer
    style["layers"].append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("LineString", "MultiLineString", "Polygon", "MultiPolygon"),
        "paint": {
            "line-color": "#3b82f6",
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.2, 12, 2.5],
            "line-opacity": 0.8
        }
    })

def sanitize_name(name):
    """Sanitizes a name for use as a layer or slug."""
    name = name.lower()
    name = (name.replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss"))
    name = name.replace(" ", "_").replace("-", "_")
    name = re.sub(r"[^a-z0-9_]", "_", name)
    return re.sub(r"_+", "_", name).strip("_")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--sprite-url", default="../assets/sprites/oe5ith-markers/sprite")
    parser.add_argument("--glyphs-url", default="https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf")
    args = parser.parse_args()
    
    manifest_path = Path(args.root) / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
    folder_rel = "NAH-Stützpunkte"
    # Sanitized slug and pmtiles path
    slug = "-".join(sanitize_name(p).replace("_", "-") for p in Path(folder_rel).parts)
    pmtiles_rel = f"pmtiles/{slug}.pmtiles"
    pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
    
    style = create_base_style("OE5ITH NAH-Stützpunkte", pmtiles_url, args.sprite_url, args.glyphs_url)
    style["metadata"]["folder"] = folder_rel
    
    # Wir scannen den Ordner nach geojson Dateien um die Layer Namen zu bekommen
    nah_dir = Path(args.root) / folder_rel
    if not nah_dir.exists():
        print(f"⚠️ Ordner {nah_dir} nicht gefunden.")
        return

    for g in sorted(nah_dir.glob("*.geojson")):
        layer_name = g.stem
        # Wir müssen den Layer-Namen so transformieren wie im pmtiles_builder.py
        source_layer = sanitize_name(layer_name)
        
        ltype = get_layer_type(manifest, layer_name, folder_rel)
        
        if ltype == "point":
            add_nah_point_layer(style, source_layer)
        elif ltype == "polygon":
            add_nah_polygon_layer(style, source_layer)
        else:
            # Fallback: Versuche beides wenn unbekannt
            add_nah_polygon_layer(style, source_layer)
            add_nah_point_layer(style, source_layer)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular with Manifest)")

if __name__ == "__main__": main()
