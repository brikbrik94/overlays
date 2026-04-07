#!/usr/bin/env bash
set -euo pipefail

# Modulares Skript für den PMTiles-Build
# Nutzt pmtiles_builder.py zur Konvertierung von GeoJSON -> PMTiles

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL_DATA_DIR="$ROOT_DIR/external/geojson-data"
OUT_DIR="$ROOT_DIR/dist"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --root <path>  Custom GeoJSON root (default: $EXTERNAL_DATA_DIR)
  --out <path>   Output directory (default: $OUT_DIR)
  -h, --help     Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) EXTERNAL_DATA_DIR="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ ! -d "$EXTERNAL_DATA_DIR" ]]; then
  echo "❌ External data directory not found: $EXTERNAL_DATA_DIR"
  exit 1
fi

PYTHON_BIN="python3"
[[ ! -x "$(command -v python3)" ]] && PYTHON_BIN="python"

echo "🚀 Starting modular PMTiles build..."
"$PYTHON_BIN" "$ROOT_DIR/scripts/pmtiles_builder.py" --root "$EXTERNAL_DATA_DIR" --out "$OUT_DIR"

echo
echo "✅ PMTiles build complete. Files are in: $OUT_DIR/pmtiles"
