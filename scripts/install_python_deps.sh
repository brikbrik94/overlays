#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
REQ_FILE="${ROOT_DIR}/scripts/requirements-sprite-tools.txt"
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--venv <path>] [--requirements <path>] [--dry-run]

Creates a Python virtual environment and installs required packages there.
This avoids Debian 13 "externally-managed-environment" issues with global pip.

Options:
  --venv <path>          Target virtualenv directory (default: ${ROOT_DIR}/.venv)
  --requirements <path>  Requirements file (default: ${REQ_FILE})
  --dry-run              Print commands without executing installs
  -h, --help             Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --requirements)
      REQ_FILE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Requirements file not found: $REQ_FILE" >&2
  exit 1
fi

echo "Using virtualenv: $VENV_DIR"
echo "Using requirements: $REQ_FILE"

if [[ $DRY_RUN -eq 1 ]]; then
  cat <<CMDS
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$REQ_FILE"
CMDS
  exit 0
fi

python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$REQ_FILE"

echo
echo "Done. Activate with:"
echo "  source "$VENV_DIR/bin/activate""
echo "Then run, e.g.:"
echo "  python scripts/convert_sprite_svgs.py --source assets/sprites --out assets/sprites/png"
echo "  python scripts/build_sprites.py --source assets/sprites/png --out dist/assets/sprites"
