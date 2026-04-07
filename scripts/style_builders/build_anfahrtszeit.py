#!/usr/bin/env python3
import argparse, os, json, re
from pathlib import Path
from style_utils import create_base_style, build_pmtiles_source_url, write_style, geometry_filter, DEFAULT_SOURCE_ID

ANFAHRTSZEIT_COLOR_RAMP = ["#22c55e", "#84cc16", "#eab308", "#f59e0b", "#f97316", "#dc2626"]

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

def anfahrtszeit_sort_key(layer_name):
    parts = [int(part) for part in re.findall(r"\d+", layer_name)]
    if len(parts) >= 2:
        return (max(parts[0], parts[1]), min(parts[0], parts[1]))
    if parts:
        return (parts[0], parts[0])
    return (10**9, 10**9)

def pick_palette_color(palette, index, total):
    if total <= 1:
        return palette[0]
    if total <= len(palette):
        palette_index = int(round(index * (len(palette) - 1) / (total - 1)))
        return palette[palette_index]
    return palette[index % len(palette)]

def add_anfahrtszeit_layers(style, source_layer, color):
    base_id = f"anfahrtszeit-{source_layer}"
    
    # Fill Layer
    style["layers"].append({
        "id": f"{base_id}-fill",
        "type": "fill",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Polygon", "MultiPolygon"),
        "paint": {
            "fill-color": color,
            "fill-opacity": 0.25,
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
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.2, 12, 2.5],
            "line-opacity": 0.8
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
    
    # Wir bearbeiten aktuell nur "Anfahrtszeit/Linz"
    folder_rel = "Anfahrtszeit/Linz"
    slug = "-".join(sanitize_name(p).replace("_", "-") for p in Path(folder_rel).parts)
    pmtiles_rel = f"pmtiles/{slug}.pmtiles"
    pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
    
    style = create_base_style(f"OE5ITH {folder_rel}", pmtiles_url, args.sprite_url, args.glyphs_url)
    style["metadata"]["folder"] = folder_rel
    style["metadata"]["colorStrategy"] = "travel-time-ramp"
    
    # Scannen
    base_dir = Path(args.root) / folder_rel
    if not base_dir.exists():
        print(f"⚠️ Ordner {base_dir} nicht gefunden.")
        return

    geojson_files = sorted(base_dir.glob("*.geojson"), key=lambda p: anfahrtszeit_sort_key(p.stem))
    total = len(geojson_files)
    
    for index, g in enumerate(geojson_files):
        layer_name = g.stem
        source_layer = sanitize_name(layer_name)
        color = pick_palette_color(ANFAHRTSZEIT_COLOR_RAMP, index, total)
        add_anfahrtszeit_layers(style, source_layer, color)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular with Color Ramp)")

if __name__ == "__main__": main()
