#!/usr/bin/env python3
import json, os, re, subprocess, tempfile, argparse
from pathlib import Path

# --- Pin Derivation Logic (from build_hosted_overlays.py) ---

def truthy_value(value):
    if isinstance(value, bool): return value
    if isinstance(value, (int, float)): return value != 0
    if isinstance(value, str): return value.strip().lower() in {"1", "true", "yes", "y", "ja"}
    return False

def derive_rd_pin(properties):
    emergency = str(properties.get("emergency", "")).strip().lower()
    if emergency == "mountain_rescue": return "brd-pin"
    if emergency != "ambulance_station": return "fallback-pin"
    has_nef = truthy_value(properties.get("ambulance_station:emergency_doctor"))
    has_rd = truthy_value(properties.get("ambulance_station:patient_transport"))
    pin_prefix = "nef" if has_nef else "rd" if (has_rd or emergency == "ambulance_station") else "fallback-pin"
    if pin_prefix == "fallback-pin": return "fallback-pin"
    
    brand_short = str(properties.get("brand:short", "")).strip().lower()
    mapping = {"brk":"brk", "örk":"oerk", "oerk":"oerk", "asb":"asb", "mhd":"mhd", "juh":"juh", "gk":"gk", "ma70":"ma70", "ims":"ims", "stadler":"stadler"}
    suffix = mapping.get(brand_short)
    if not suffix:
        text = " ".join(str(properties.get(k, "")).lower() for k in ("brand", "operator", "name", "short_name"))
        for k, v in mapping.items():
            if k in text: suffix = v; break
    return f"{pin_prefix}-{suffix}" if suffix else "fallback-pin"

def derive_nah_pin(properties):
    if str(properties.get("emergency", "")).lower() != "air_rescue_service": return "fallback-pin"
    text = " ".join(str(properties.get(k, "")).lower() for k in ("brand", "operator", "name", "short_name", "description", "alt_name"))
    rules = [("nah-adac-luftrettung", ("adac",)), ("nah-drf-luftrettung", ("drf",)), ("nah-oeamtc-flugrettung", ("oeamtc", "christophorus")), 
             ("nah-martin-flugrettung", ("martin flugrettung", "heli austria")), ("nah-schenk-air", ("schenkair", "schenk air")), 
             ("nah-ara-flugrettung", ("ara luftrettung",)), ("nah-wucher-helicopter", ("wucher",)), 
             ("nah-shs-schider-helicopter-service", ("schider", "shs")), ("nah-bundesministerium-des-inneren", ("bundesministerium des inneren", "polizei", "libelle"))]
    for pin, needles in rules:
        if any(n in text for n in needles): return pin
    return "fallback-pin"

# --- Build Logic ---

def process_geojson(src, dst, folder_slug):
    data = json.loads(src.read_text(encoding="utf-8"))
    for f in data.get("features", []):
        props = f.setdefault("properties", {})
        if folder_slug == "rd-dienststellen": props["pin"] = derive_rd_pin(props)
        elif folder_slug == "nah-stuetzpunkte": props["pin"] = derive_nah_pin(props)
    dst.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

def run_tippecanoe(out_file, layer_specs, folder_slug):
    # -Z 0 -z 15: Zoomstufen 0 bis 15
    # --force: Bestehende Dateien überschreiben
    # --no-feature-limit & --no-tile-size-limit: Verhindert das Verwerfen von Features bei Größenüberschreitung
    # -r 1: Verhindert das automatische Ausdünnen (Dropping) von Punkten bei niedrigen Zoomstufen
    cmd = ["tippecanoe", "-o", str(out_file), "-Z", "0", "-z", "15", "--force", "--no-feature-limit", "--no-tile-size-limit", "-r", "1"]
    
    # Spezifische Optimierungen für NAH
    if folder_slug == "nah-stuetzpunkte":
        cmd.extend(["--no-line-simplification", "--no-tiny-polygon-reduction"])
    
    for layer_name, file_path in layer_specs:
        cmd.extend(["-L", f"{layer_name}:{file_path}"])
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    
    root = Path(args.root).resolve()
    out_base = Path(args.out).resolve() / "pmtiles"
    
    for bundle_dir in [d for d in root.rglob("*") if d.is_dir() and list(d.glob("*.geojson"))]:
        rel_path = bundle_dir.relative_to(root)
        # Sanitized filename for PMTiles (Flat slug)
        slug = "-".join(sanitize_name(p).replace("_", "-") for p in rel_path.parts)
        out_file = out_base / f"{slug}.pmtiles"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📦 Building bundle: {rel_path} -> {slug}.pmtiles")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            specs = []
            for g in sorted(bundle_dir.glob("*.geojson")):
                clean_name = sanitize_name(g.stem)
                target = tmp_path / g.name
                process_geojson(g, target, slug)
                specs.append((clean_name, target))
            
            run_tippecanoe(out_file, specs, slug)

if __name__ == "__main__": main()
