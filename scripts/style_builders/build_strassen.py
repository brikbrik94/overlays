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

def add_road_layers(style, source_layer, line_color, bubble_icon, text_color):
    base_id = f"road-{source_layer}"
    
    # 1. Line Layer
    style["layers"].append({
        "id": f"{base_id}-line",
        "type": "line",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("LineString", "MultiLineString"),
        "layout": {
            "line-join": "round",
            "line-cap": "round"
        },
        "paint": {
            "line-color": line_color,
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.5, 12, 4.0],
            "line-opacity": 0.8
        }
    })
    
    # 2. Label Layer (Road Shields along the line)
    style["layers"].append({
        "id": f"{base_id}-labels",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": ["all",
            geometry_filter("LineString", "MultiLineString"),
            ["has", "ref"]
        ],
        "layout": {
            "text-field": ["get", "ref"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 8, 8.5, 12, 10],
            "text-font": DEFAULT_FONT_STACK,
            "symbol-placement": "line",
            "symbol-spacing": 100,
            "symbol-avoid-edges": False,
            "text-max-angle": 80,
            "text-rotation-alignment": "viewport",
            "text-pitch-alignment": "viewport",
            "icon-image": bubble_icon,
            "icon-text-fit": "both",
            "icon-text-fit-padding": [1, 2, 1, 2],
            "icon-allow-overlap": False,
            "text-allow-overlap": False,
            "text-padding": 1,
            "icon-padding": 1
        },
        "paint": {
            "text-color": text_color,
            "icon-opacity": 0.9
        }
    })

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--folder", required=True, help="e.g. Straßen/Autobahnen")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--line-color", default="#3b82f6")
    parser.add_argument("--bubble-icon", default="label-bubble")
    parser.add_argument("--text-color", default="#111827")
    parser.add_argument("--sprite-url", default="../assets/sprites/oe5ith-markers/sprite")
    parser.add_argument("--glyphs-url", default="https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf")
    args = parser.parse_args()
    
    folder_rel = args.folder
    # slug should be strassen-autobahnen or strassen-bundesstrassen
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
        add_road_layers(style, source_layer, args.line_color, args.bubble_icon, args.text_color)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular Road Style)")

if __name__ == "__main__": main()
