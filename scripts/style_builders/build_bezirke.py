#!/usr/bin/env python3
import argparse, os, json, re
from pathlib import Path
from style_utils import create_base_style, build_pmtiles_source_url, write_style, geometry_filter, DEFAULT_SOURCE_ID, DEFAULT_FONT_STACK

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

def add_bezirke_layers(style, source_layer):
    base_id = f"bezirke-{source_layer}"
    
    # 1. Fill Layer
    style["layers"].append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "paint": {
            "fill-color": "#3b82f6",
            "fill-opacity": 0.05,
            "fill-outline-color": "transparent"
        }
    })
    
    # 2. Line Layer (Outline)
    style["layers"].append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("LineString", "MultiLineString", "Polygon", "MultiPolygon"),
        "paint": {
            "line-color": "#3b82f6",
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.0, 12, 2.5],
            "line-opacity": 0.6,
            "line-dasharray": [2, 2]
        }
    })
    # 3. Label Layer (Centroid labels, matching layer color)
    style["layers"].append({
        "id": f"{base_id}-labels",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "layout": {
            "text-field": ["get", "name"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 8, 11, 12, 15],
            "text-font": ["Open-Sans-Bold"],
            "text-allow-overlap": False,
            "text-padding": 10,
            "symbol-placement": "point"
        },
        "paint": {
            "text-color": "#3b82f6"
        }
    })

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--sprite-url", default="../assets/sprites/oe5ith-markers/sprite")
    parser.add_argument("--glyphs-url", default="https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf")
    args = parser.parse_args()
    
    folder_rel = "Bezirke"
    slug = "-".join(sanitize_name(p).replace("_", "-") for p in Path(folder_rel).parts)
    pmtiles_rel = f"pmtiles/{slug}.pmtiles"
    pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
    
    style = create_base_style(f"OE5ITH {folder_rel}", pmtiles_url, args.sprite_url, args.glyphs_url)
    style["metadata"]["folder"] = folder_rel
    
    # Scannen (Hier ist es meist nur Bezirke.geojson)
    base_dir = Path(args.root) / folder_rel
    if not base_dir.exists():
        print(f"⚠️ Directory {base_dir} not found.")
        return

    for g in sorted(base_dir.glob("*.geojson")):
        source_layer = sanitize_name(g.stem)
        add_bezirke_layers(style, source_layer)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular with Centroid Labels)")

if __name__ == "__main__": main()
