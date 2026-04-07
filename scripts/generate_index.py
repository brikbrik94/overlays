#!/usr/bin/env python3
import json, argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--base-url", default="")
    args = parser.parse_args()
    
    out_dir = Path(args.out).resolve()
    styles_dir = out_dir / "styles"
    pmtiles_dir = out_dir / "pmtiles"
    
    index_entries = []
    
    # Wir scannen alle .style.json Dateien im styles Ordner
    for style_file in sorted(styles_dir.glob("*.style.json")):
        slug = style_file.stem
        
        with open(style_file, "r", encoding="utf-8") as f:
            style = json.load(f)
            # Metadaten auslesen
            folder = style.get("metadata", {}).get("folder", slug)
            
            # Layer zählen (alle außer Background und OSM)
            layers = style.get("layers", [])
            source_layer_count = len(set(l.get("source-layer") for l in layers if l.get("source-layer")))
            
            # PMTiles Pfad ermitteln (relativ zu dist)
            # Wir suchen die PMTiles Datei, die im Source-URL steht
            pmtiles_url = ""
            for source in style.get("sources", {}).values():
                if source.get("type") == "vector" and "url" in source:
                    pmtiles_url = source["url"]
                    break
            
            # Wir extrahieren den relativen Pfad aus pmtiles://...
            pmtiles_rel = ""
            if pmtiles_url.startswith("pmtiles://"):
                # Format: pmtiles://../pmtiles/folder.pmtiles oder pmtiles://host/pmtiles/folder.pmtiles
                path_part = pmtiles_url.replace("pmtiles://", "")
                if path_part.startswith("../"):
                    pmtiles_rel = path_part.replace("../", "")
                elif "/" in path_part:
                    pmtiles_rel = "/".join(path_part.split("/")[1:])
            
            # Fallback falls Extraktion fehlschlägt
            if not pmtiles_rel:
                pmtiles_rel = f"pmtiles/{slug}.pmtiles"

        index_entries.append({
            "folder": folder,
            "label": folder,
            "styleFile": f"styles/{style_file.name}",
            "pmtilesFile": pmtiles_rel,
            "sourceLayerCount": source_layer_count
        })
        
    index_path = styles_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_entries, f, indent=2, ensure_ascii=False)
    
    print(f"✅ index.json created with {len(index_entries)} entries.")

if __name__ == "__main__": main()
