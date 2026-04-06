#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_LOCAL_ROOT="$ROOT_DIR/geojson"
DEFAULT_EXTERNAL_ROOT="$ROOT_DIR/external/geojson-data"
DEFAULT_OUT_DIR="$ROOT_DIR/dist"

SOURCE_MODE=""
CUSTOM_ROOT=""
OUT_DIR="$DEFAULT_OUT_DIR"
CLEAN_MODE=""
REBUILD_SPRITES=""
SKIP_PMTILES=0

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Interactive wrapper to simplify overlay builds.

Options:
  --source <local|external|custom>  Data source mode
  --root <path>                     Custom data root (implies --source custom)
  --out <path>                      Output directory (default: $DEFAULT_OUT_DIR)
  --clean <yes|no>                  Clean output directory before build
  --sprites <yes|no>                Rebuild sprites before build
  --skip-pmtiles                    Build only manifests/styles/index (no tippecanoe)
  -h, --help                        Show this help
USAGE
}

ask_yes_no() {
  local prompt="$1"
  local default="$2"
  local answer
  while true; do
    read -r -p "$prompt" answer
    answer="${answer:-$default}"
    case "${answer,,}" in
      y|yes|ja) echo "yes"; return 0 ;;
      n|no|nein) echo "no"; return 0 ;;
      *) echo "Bitte yes/no bzw. y/n eingeben." ;;
    esac
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE_MODE="$2"
      shift 2
      ;;
    --root)
      SOURCE_MODE="custom"
      CUSTOM_ROOT="$2"
      shift 2
      ;;
    --out)
      OUT_DIR="$2"
      shift 2
      ;;
    --clean)
      CLEAN_MODE="$2"
      shift 2
      ;;
    --sprites)
      REBUILD_SPRITES="$2"
      shift 2
      ;;
    --skip-pmtiles)
      SKIP_PMTILES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$SOURCE_MODE" ]]; then
  echo "Welche Datenquelle möchtest du verwenden?"
  echo "  1) local    ($DEFAULT_LOCAL_ROOT)"
  echo "  2) external ($DEFAULT_EXTERNAL_ROOT)"
  echo "  3) custom"
  read -r -p "Auswahl [1/2/3] (default 1): " choice
  case "${choice:-1}" in
    1) SOURCE_MODE="local" ;;
    2) SOURCE_MODE="external" ;;
    3) SOURCE_MODE="custom" ;;
    *) echo "Ungültige Auswahl: ${choice}"; exit 2 ;;
  esac
fi

case "$SOURCE_MODE" in
  local)
    DATA_ROOT="$DEFAULT_LOCAL_ROOT"
    ;;
  external)
    DATA_ROOT="$DEFAULT_EXTERNAL_ROOT"
    ;;
  custom)
    if [[ -z "$CUSTOM_ROOT" ]]; then
      read -r -p "Pfad zum GeoJSON-Root: " CUSTOM_ROOT
    fi
    DATA_ROOT="$CUSTOM_ROOT"
    ;;
  *)
    echo "Unsupported --source value: $SOURCE_MODE" >&2
    exit 2
    ;;
esac

if [[ "$SOURCE_MODE" == "external" && ! -d "$DATA_ROOT/.git" ]]; then
  echo "ℹ️ External repo nicht vorhanden. Initialisiere es jetzt..."
  bash "$ROOT_DIR/scripts/init_external_geojson_repo.sh" --target "$DATA_ROOT"
fi

if [[ ! -d "$DATA_ROOT" ]]; then
  echo "Data root does not exist: $DATA_ROOT" >&2
  exit 2
fi

if [[ -z "$CLEAN_MODE" ]]; then
  CLEAN_MODE="$(ask_yes_no "Clean build starten? [y/N]: " "no")"
fi

if [[ -z "$REBUILD_SPRITES" ]]; then
  REBUILD_SPRITES="$(ask_yes_no "Sprites neu bauen? [y/N]: " "no")"
fi

if [[ "$REBUILD_SPRITES" =~ ^(yes|y|ja)$ ]]; then
  echo "🎨 Rebuilding sprites..."
  bash "$ROOT_DIR/scripts/run_sprite_pipeline.sh"
fi

BUILD_CMD=(python "$ROOT_DIR/build_hosted_overlays.py" --root "$DATA_ROOT" --out "$OUT_DIR")
if [[ "$CLEAN_MODE" =~ ^(yes|y|ja)$ ]]; then
  BUILD_CMD+=(--clean)
fi
if [[ "$SKIP_PMTILES" -eq 1 ]]; then
  BUILD_CMD+=(--skip-pmtiles)
fi

echo "\n🚀 Running build: ${BUILD_CMD[*]}"
"${BUILD_CMD[@]}"

echo

echo "✅ Build complete. Output: $OUT_DIR"
