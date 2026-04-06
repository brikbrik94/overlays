#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_REPO_URL="git@github.com:brikbrik94/geojson.git"
DEFAULT_TARGET_DIR="$ROOT_DIR/external/geojson-data"

REPO_URL="$DEFAULT_REPO_URL"
TARGET_DIR="$DEFAULT_TARGET_DIR"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--repo <git-url>] [--target <path>] [--refresh]

Clones (or updates) the external GeoJSON repository used by overlay builds.

Options:
  --repo     Git URL of the GeoJSON repository (default: $DEFAULT_REPO_URL)
  --target   Local checkout directory (default: $DEFAULT_TARGET_DIR)
  --refresh  If target exists, fetch and fast-forward pull
  -h, --help Show this help
USAGE
}

DO_REFRESH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --target)
      TARGET_DIR="$2"
      shift 2
      ;;
    --refresh)
      DO_REFRESH=1
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

if [[ -d "$TARGET_DIR/.git" ]]; then
  echo "✅ External repo already exists: $TARGET_DIR"
  if [[ "$DO_REFRESH" -eq 1 ]]; then
    echo "🔄 Refreshing repository..."
    git -C "$TARGET_DIR" fetch --all --prune
    git -C "$TARGET_DIR" pull --ff-only
  fi
else
  mkdir -p "$(dirname "$TARGET_DIR")"
  echo "⬇️ Cloning $REPO_URL -> $TARGET_DIR"
  git clone "$REPO_URL" "$TARGET_DIR"
fi

GEOJSON_COUNT="$(find "$TARGET_DIR" -maxdepth 3 -type f -name '*.geojson' | wc -l | tr -d ' ')"
if [[ "$GEOJSON_COUNT" -eq 0 ]]; then
  echo "⚠️ No .geojson files found under $TARGET_DIR (maxdepth=3)."
else
  echo "✅ Found $GEOJSON_COUNT GeoJSON files under $TARGET_DIR"
fi

echo
echo "Next step:"
echo "  bash $ROOT_DIR/run.sh --source external"
