#!/usr/bin/env python3
import argparse, os, json, re
from pathlib import Path
from style_utils import create_base_style, build_pmtiles_source_url, write_style, geometry_filter, DEFAULT_SOURCE_ID, DEFAULT_FONT_STACK

LEITSTELLEN_COLOR_PALETTE = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"]

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

def pick_palette_color(palette, index, total):
    if total <= 1:
        return palette[0]
    if total <= len(palette):
        # Evenly spread colors from the palette
        palette_index = int(round(index * (len(palette) - 1) / (total - 1)))
        return palette[palette_index]
    return palette[index % len(palette)]

def add_leitstellen_layers(style, source_layer, color):
    base_id = f"leitstelle-{source_layer}"
    
    # Fill Layer
    style["layers"].append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "paint": {
            "fill-color": color,
            "fill-opacity": 0.2,
            "fill-outline-color": color
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
            "line-color": color,
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.5, 12, 3.5],
            "line-opacity": 0.8
        }
    })
    
    # Label Layer (Centroid labels, matching layer color)
    style["layers"].append({
        "id": f"{base_id}-labels",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "layout": {
            "text-field": source_layer.upper(), # HRV, INN, etc.
            "text-size": ["interpolate", ["linear"], ["zoom"], 8, 12, 12, 18],
            "text-font": DEFAULT_FONT_STACK,
            "text-allow-overlap": False,
            "symbol-placement": "point"
        },
        "paint": {
            "text-color": color,
            "text-halo-color": "#ffffff",
            "text-halo-width": 2.0,
            "text-halo-blur": 0.5
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
    
    folder_rel = "Leitstellen-Bereiche"
    slug = "-".join(sanitize_name(p).replace("_", "-") for p in Path(folder_rel).parts)
    pmtiles_rel = f"pmtiles/{slug}.pmtiles"
    pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
    
    style = create_base_style(f"OE5ITH {folder_rel}", pmtiles_url, args.sprite_url, args.glyphs_url)
    style["metadata"]["folder"] = folder_rel
    style["metadata"]["colorStrategy"] = "source-layer-palette"
    
    # Scan directory
    base_dir = Path(args.root) / folder_rel
    if not base_dir.exists():
        print(f"⚠️ Directory {base_dir} not found.")
        return

    geojson_files = sorted(base_dir.glob("*.geojson"))
    total = len(geojson_files)
    
    for index, g in enumerate(geojson_files):
        layer_name = g.stem
        source_layer = sanitize_name(layer_name)
        color = pick_palette_color(LEITSTELLEN_COLOR_PALETTE, index, total)
        add_leitstellen_layers(style, source_layer, color)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular with Palette)")

if __name__ == "__main__": main()
