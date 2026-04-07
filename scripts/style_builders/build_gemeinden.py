#!/usr/bin/env python3
import argparse, os, json, re
from pathlib import Path
from style_utils import create_base_style, build_pmtiles_source_url, write_style, geometry_filter, DEFAULT_SOURCE_ID

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

def add_gemeinden_layers(style, source_layer):
    base_id = f"gemeinde-{source_layer}"
    
    # 1. Fill Layer (Very light blue)
    style["layers"].append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "paint": {
            "fill-color": "#3b82f6",
            "fill-opacity": 0.02,
            "fill-outline-color": "transparent"
        }
    })
    
    # 2. Line Layer (Thin blue boundary)
    style["layers"].append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("LineString", "MultiLineString", "Polygon", "MultiPolygon"),
        "paint": {
            "line-color": "#3b82f6",
            "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 13, 1.5],
            "line-opacity": 0.4
        }
    })
    
    # 3. Label Layer (Centered labels)
    style["layers"].append({
        "id": f"{base_id}-labels-center",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "layout": {
            "text-field": ["get", "name"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 1, 8, 12, 11],
            "text-font": ["Open-Sans-Bold"],
            "text-allow-overlap": False,
            "text-padding": 10,
            "text-max-width": 8,
            "symbol-placement": "point"
        },
        "paint": {
            "text-color": "#3b82f6",
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.0,
            "text-halo-blur": 0.5
        }
    })

    # 4. Label Layer (Repeating labels along boundaries)
    style["layers"].append({
        "id": f"{base_id}-labels-repeat",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "layout": {
            "text-field": ["get", "name"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 1, 8, 12, 14],
            "text-font": ["Open-Sans-Bold"],
            "text-allow-overlap": False,
            "text-padding": 5,
            "text-max-width": 10,
            "symbol-placement": "line",
            "symbol-spacing": 350,
            "text-rotation-alignment": "viewport"
        },
        "paint": {
            "text-color": "#3b82f6",
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.2,
            "text-halo-blur": 0.5,
            "text-opacity": 0.8
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
    
    folder_rel = "Gemeinden"
    slug = "-".join(sanitize_name(p).replace("_", "-") for p in Path(folder_rel).parts)
    pmtiles_rel = f"pmtiles/{slug}.pmtiles"
    pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
    
    style = create_base_style(f"OE5ITH {folder_rel}", pmtiles_url, args.sprite_url, args.glyphs_url)
    style["metadata"]["folder"] = folder_rel
    
    base_dir = Path(args.root) / folder_rel
    if not base_dir.exists():
        print(f"⚠️ Directory {base_dir} not found.")
        return

    # Process all GeoJSONs in this folder as source layers
    for g in sorted(base_dir.glob("*.geojson")):
        source_layer = sanitize_name(g.stem)
        add_gemeinden_layers(style, source_layer)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular Gemeinden Style)")

if __name__ == "__main__": main()
