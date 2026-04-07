#!/usr/bin/env python3
import json
from pathlib import Path

# --- Konstanten für das gesamte Projekt ---
ACCENT = "#3b82f6"
BACKGROUND = "#1a1a1a"
BORDER = "#333333"
TEXT = "#e0e0e0"
HALO = "#1a1a1a"
LABEL_TEXT = "#111111"
LABEL_BUBBLE = "#ffffff"
DEFAULT_MAXZOOM = 15
DEFAULT_FONT_STACK = ["Noto-Sans-Regular"]
DEFAULT_SOURCE_ID = "folder"

def build_pmtiles_source_url(base_url, pmtiles_relpath):
    rel = Path(pmtiles_relpath).as_posix()
    if base_url:
        return f"pmtiles://{base_url.rstrip('/')}/{rel}"
    return f"pmtiles://../{rel}"

def write_style(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def create_base_style(name, pmtiles_url, sprite_url, glyphs_url):
    return {
        "version": 8,
        "name": name,
        "metadata": {
            "generator": "modular_style_builder",
        },
        "sources": {
            DEFAULT_SOURCE_ID: {
                "type": "vector",
                "url": pmtiles_url,
                "minzoom": 0,
                "maxzoom": DEFAULT_MAXZOOM,
            }
        },
        "glyphs": glyphs_url,
        "sprite": sprite_url,
        "layers": [
            {
                "id": "background",
                "type": "background",
                "paint": {"background-color": BACKGROUND},
            }
        ]
    }

def geometry_filter(*geometry_types):
    return ["match", ["geometry-type"], list(geometry_types), True, False]
