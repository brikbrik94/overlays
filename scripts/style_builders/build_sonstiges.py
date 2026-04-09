#!/usr/bin/env python3
import argparse, os, json, re
from pathlib import Path
from style_utils import create_base_style, build_pmtiles_source_url, write_style, geometry_filter, DEFAULT_SOURCE_ID, DEFAULT_FONT_STACK

# --- Konfiguration aus linien.json (Website) ---
LINIE_CONFIG = {
    "stylesByType": {
        "tram": {"strokeWidth": 4, "zIndex": 4},
        "poestlingbergbahn": {"strokeWidth": 4, "zIndex": 4},
        "bus": {"strokeWidth": 3, "zIndex": 3},
        "schnellbus": {"color": "#8B5A2B", "strokeWidth": 2, "zIndex": 2},
        "stadtteillinie": {"color": "#8BC34A", "strokeWidth": 2, "zIndex": 2}
    },
    "linien": {
        "1": {"color": "#E61E58", "type": "tram", "offset": -6},
        "2": {"color": "#BDA5D9", "type": "tram", "offset": -2},
        "3": {"color": "#5B1A80", "type": "tram", "offset": 2},
        "4": {"color": "#E11E26", "type": "tram", "offset": 6},
        "50": {"color": "#0BA34A", "type": "poestlingbergbahn", "offset": 10},
        "11": {"color": "#F39C12", "type": "bus", "offset": 0},
        "12": {"color": "#2ECC71", "type": "bus", "offset": 0},
        "17": {"color": "#F1C40F", "type": "bus", "offset": 0},
        "18": {"color": "#3498DB", "type": "bus", "offset": 0},
        "19": {"color": "#E74C3C", "type": "bus", "offset": 0},
        "25": {"color": "#D4A86F", "type": "bus", "offset": 0},
        "26": {"color": "#2C82C9", "type": "bus", "offset": 0},
        "27": {"color": "#27AE60", "type": "bus", "offset": 0},
        "33": {"color": "#E6B0AA", "type": "bus", "offset": 0},
        "33a": {"color": "#AF7AC5", "type": "bus", "offset": 0},
        "38": {"color": "#D35400", "type": "bus", "offset": 0},
        "41": {"color": "#C0392B", "type": "bus", "offset": 0},
        "43": {"color": "#1C6EA4", "type": "bus", "offset": 0},
        "45": {"color": "#A93226", "type": "bus", "offset": 0},
        "45a": {"color": "#F1948A", "type": "bus", "offset": 0},
        "46": {"color": "#5DADE2", "type": "bus", "offset": 0}
    }
}

DEFAULT_LINE_COLOR = "#1d4ed8"
DEFAULT_LINE_WIDTH = 2.5

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

def parse_line_id(name):
    """Extracts the line ID from a name like 'Linie-1' or 'linie101'."""
    match = re.search(r"(\d+[a-z]?)", name, re.IGNORECASE)
    return match.group(1).lower() if match else None

def resolve_line_style(line_id):
    if not line_id:
        return {"color": DEFAULT_LINE_COLOR, "width": DEFAULT_LINE_WIDTH}
    
    entry = LINIE_CONFIG["linien"].get(line_id, {})
    line_type = entry.get("type")
    type_entry = LINIE_CONFIG["stylesByType"].get(line_type, {}) if line_type else {}
    
    # Schnellbus/Stadtteillinie Regeln (falls nicht explizit in 'linien' definiert)
    if not line_type:
        if re.match(r"^[sn]\d+", line_id): # S-Bus, N-Bus
            type_entry = LINIE_CONFIG["stylesByType"].get("schnellbus", {})
        elif re.match(r"^\d{3,}", line_id): # Stadtteillinien oft 3-stellig
            type_entry = LINIE_CONFIG["stylesByType"].get("stadtteillinie", {})

    color = entry.get("color") or type_entry.get("color") or DEFAULT_LINE_COLOR
    width = entry.get("strokeWidth") or type_entry.get("strokeWidth") or DEFAULT_LINE_WIDTH
    offset = entry.get("offset") or type_entry.get("offset") or 0
    
    return {"color": color, "width": width, "offset": offset}

def add_line_layers(style, source_layer, line_id):
    line_style = resolve_line_style(line_id)
    base_id = f"sonstiges-{source_layer}"
    
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
            "line-color": line_style["color"],
            "line-width": ["interpolate", ["linear"], ["zoom"], 10, line_style["width"] * 0.5, 14, line_style["width"]],
            "line-offset": line_style["offset"],
            "line-opacity": 0.85
        }
    })
    
    # 2. Label Layer (Linien-Nummer)
    style["layers"].append({
        "id": f"{base_id}-labels",
        "type": "symbol",
        "source": DEFAULT_SOURCE_ID,
        "source-layer": source_layer,
        "filter": geometry_filter("LineString", "MultiLineString"),
        "layout": {
            "text-field": line_id.upper() if line_id else ["get", "name"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 10, 9, 14, 11],
            "text-font": DEFAULT_FONT_STACK,
            "symbol-placement": "line",
            "symbol-spacing": 300,
            "text-rotation-alignment": "viewport",
            "text-keep-upright": True
        },
        "paint": {
            "text-color": line_style["color"],
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.5,
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
    
    folder_rel = "Sonstiges"
    slug = "-".join(sanitize_name(p).replace("_", "-") for p in Path(folder_rel).parts)
    pmtiles_rel = f"pmtiles/{slug}.pmtiles"
    pmtiles_url = build_pmtiles_source_url(args.base_url, pmtiles_rel)
    
    style = create_base_style(f"OE5ITH {folder_rel}", pmtiles_url, args.sprite_url, args.glyphs_url)
    style["metadata"]["folder"] = folder_rel
    
    base_dir = Path(args.root) / folder_rel
    if not base_dir.exists():
        print(f"⚠️ Directory {base_dir} not found.")
        return

    for g in sorted(base_dir.glob("*.geojson")):
        source_layer = sanitize_name(g.stem)
        line_id = parse_line_id(g.stem)
        add_line_layers(style, source_layer, line_id)
        
    write_style(Path(args.out) / "styles" / f"{slug}.style.json", style)
    print(f"✅ Style created: {slug} (Modular Sonstiges Style)")

if __name__ == "__main__": main()
