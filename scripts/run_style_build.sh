#!/usr/bin/env bash
set -euo pipefail

# Hauptskript für den modularen Style-Build
# Ruft die einzelnen Style-Builder in scripts/style_builders/ auf

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL_DATA_DIR="$ROOT_DIR/external/geojson-data"
OUT_DIR="$ROOT_DIR/dist"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --root <path>  External GeoJSON root (default: $EXTERNAL_DATA_DIR)
  --out <path>   Output directory (default: $OUT_DIR)
  --base-url <url> Public base URL for PMTiles references
  -h, --help     Show this help
USAGE
}

BASE_URL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) EXTERNAL_DATA_DIR="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

mkdir -p "$OUT_DIR/styles"

# Python Pfad setzen damit style_utils gefunden wird
export PYTHONPATH="$ROOT_DIR/scripts/style_builders:${PYTHONPATH:-}"

echo "🚀 Starting modular Style build..."

# Liste der Builder (hier fügen wir schrittweise neue hinzu)
BUILDERS=("build_nah.py" "build_rd.py" "build_zonen.py" "build_anfahrtszeit.py" "build_leitstellen.py" "build_bezirke.py" "build_gemeinden.py" "build_sonstiges.py")

for builder in "${BUILDERS[@]}"; do
  python3 "$ROOT_DIR/scripts/style_builders/$builder" --root "$EXTERNAL_DATA_DIR" --out "$OUT_DIR" --base-url "$BASE_URL"
done

# Straßen (Speziell aufgerufen wegen unterschiedlicher Farben)
python3 "$ROOT_DIR/scripts/style_builders/build_strassen.py" --root "$EXTERNAL_DATA_DIR" --out "$OUT_DIR" --base-url "$BASE_URL" \
  --folder "Straßen/Autobahnen" --line-color "#005fb8" --bubble-icon "label-bubble-blue" --text-color "#ffffff"

python3 "$ROOT_DIR/scripts/style_builders/build_strassen.py" --root "$EXTERNAL_DATA_DIR" --out "$OUT_DIR" --base-url "$BASE_URL" \
  --folder "Straßen/Bundesstraßen" --line-color "#ffcc00" --bubble-icon "label-bubble-yellow" --text-color "#000000"

# Index generieren
echo "📇 Generating index.json..."
python3 "$ROOT_DIR/scripts/generate_index.py" --out "$OUT_DIR" --base-url "$BASE_URL"

# Manifest generieren
echo "📜 Generating manifest.json for external scripts..."
python3 "$ROOT_DIR/scripts/generate_manifest.py"

echo
echo "✅ Style build complete. Styles, index.json and manifest.json are ready."
