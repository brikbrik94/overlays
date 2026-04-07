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

def add_rd_point_layer(style, source_layer):
    base_id = f"rd-{source_layer}"
    
    # Symbol Layer (Pins)
    style["layers"].append({
        "id": f"{base_id}-symbols",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("Point", "MultiPoint"),
        "layout": {
            "icon-image": ["coalesce", ["get", "pin"], "fallback-pin"],
            "icon-size": ["interpolate", ["linear"], ["zoom"], 6, 0.35, 12, 0.65],
            "icon-anchor": "bottom",
            "icon-allow-overlap": True,
            "icon-ignore-placement": True,
            "icon-padding": 0
        }
    })
    
    # Text Layer (SDF Bubble, feld 'alt_name' unter dem Pin)
    style["layers"].append({
        "id": f"{base_id}-text",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": ["all",
            geometry_filter("Point", "MultiPoint"),
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--sprite-url", default="../assets/sprites/oe5ith-markers/sprite")
    parser.add_argument("--glyphs-url", default="https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf")
    args = parser.parse_args()
    
    folder_rel = "RD-Dienststellen"
    # Sanitized slug and pmtiles path
    slug = "-".join(sanitize_name(p).replace("_", "-") for p in Path(folder_rel).parts)
    pmtiles_rel = f"pmtiles/{slug}.pmtiles"
    pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
    
    style = create_base_style("OE5ITH RD-Dienststellen", pmtiles_url, args.sprite_url, args.glyphs_url)
    style["metadata"]["folder"] = folder_rel
    
    # Wir scannen den Ordner nach geojson Dateien um die Layer Namen zu bekommen
    rd_dir = Path(args.root) / folder_rel
    if not rd_dir.exists():
        print(f"⚠️ Ordner {rd_dir} nicht gefunden.")
        return

    for g in sorted(rd_dir.glob("*.geojson")):
        layer_name = g.stem
        # Wir müssen den Layer-Namen so transformieren wie im pmtiles_builder.py
        source_layer = sanitize_name(layer_name)
        add_rd_point_layer(style, source_layer)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular)")

if __name__ == "__main__": main()
