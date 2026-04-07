#!/usr/bin/env python3
import argparse, os, json, re, copy
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

def build_color_match_expression(color_mapping: dict, fallback_color: str) -> list:
    # A MapLibre match expression on ["coalesce", ["get", "alt_name"], ["get", "name"]]
    # Mapbox syntax: ["match", input, key1, val1, key2, val2, fallback]
    expr = ["match", ["coalesce", ["get", "alt_name"], ["get", "name"]]]
    for key, color in color_mapping.items():
        expr.extend([key, color])
    expr.append(fallback_color)
    return expr

def add_zonen_layers(style, source_layer, color_expr):
    base_id = f"zonen-{source_layer}"
    
    # Fill Layer
    style["layers"].append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "paint": {
            "fill-color": copy.deepcopy(color_expr),
            "fill-opacity": 0.2,
            "fill-outline-color": "#333333"
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
            "line-color": copy.deepcopy(color_expr),
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.5, 12, 3.5],
            "line-opacity": 0.9
        }
    })
    
    # Circle Layer (if zones are points)
    style["layers"].append({
        "id": f"{base_id}-circle",
        "type": "circle",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Point", "MultiPoint"),
        "paint": {
            "circle-color": copy.deepcopy(color_expr),
            "circle-stroke-color": "#e0e0e0",
            "circle-stroke-width": 1,
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 3.5, 12, 6.5],
            "circle-opacity": 0.95
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
    
    # Lade color_mapping.json
    color_map_path = Path(__file__).resolve().parent.parent.parent / "assets" / "mappings" / "color_mapping.json"
    color_mapping = {}
    if color_map_path.exists():
        with open(color_map_path, "r", encoding="utf-8") as f:
            color_mapping = json.load(f)
    else:
        print(f"⚠️ Color Mapping nicht gefunden: {color_map_path}")
        
    color_expr = build_color_match_expression(color_mapping, "#3b82f6") # Blau als Fallback
    
    zonen_root = Path(args.root) / "Zonen"
    if not zonen_root.exists():
        print(f"⚠️ Ordner {zonen_root} nicht gefunden.")
        return
        
    # Wir durchsuchen den Zonen Ordner und seine direkten Unterordner (z.B. Zonen/X)
    directories = [zonen_root] + [d for d in zonen_root.rglob("*") if d.is_dir()]
    
    for bundle_dir in directories:
        geojsons = list(bundle_dir.glob("*.geojson"))
        if not geojsons:
            continue
            
        rel_path = bundle_dir.relative_to(Path(args.root))
        
        slug = "-".join(sanitize_name(p).replace("_", "-") for p in rel_path.parts)
        safe_rel_path = Path(*(sanitize_name(p).replace("_", "-") for p in rel_path.parts))
        pmtiles_rel = f"pmtiles/{safe_rel_path}.pmtiles"
        pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
        
        style = create_base_style(f"OE5ITH {rel_path}", pmtiles_url, args.sprite_url, args.glyphs_url)
        style["metadata"]["folder"] = str(rel_path)
        
        for g in sorted(geojsons):
            layer_name = g.stem
            source_layer = sanitize_name(layer_name)
            add_zonen_layers(style, source_layer, color_expr)
            
        write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
        print(f"✅ Style created: {slug} (Modular)")

if __name__ == "__main__": main()
