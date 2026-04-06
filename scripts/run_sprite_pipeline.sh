#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${ROOT_DIR}/.venv/bin/python"
INPUT_SVG=""
SOURCE_DIR="${ROOT_DIR}/assets/sprites"
WORK_DIR="${ROOT_DIR}/assets/sprites/work"
DIST_DIR="${ROOT_DIR}/dist/assets/sprites"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--input <preview.svg>] [--source-dir <dir>] [--work-dir <dir>] [--dist-dir <dir>] [--provider-map <json>]

Ohne --input werden automatisch alle Dateien <gruppe>-pin-sprite.svg aus --source-dir verarbeitet.
USAGE
}

PROVIDER_MAP=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT_SVG="$2"; shift 2 ;;
    --source-dir) SOURCE_DIR="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --dist-dir) DIST_DIR="$2"; shift 2 ;;
    --provider-map) PROVIDER_MAP="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ ! -x "$VENV_PY" ]]; then
  echo "Local .venv not found. Running dependency installer..."
  bash "$ROOT_DIR/scripts/install_python_deps.sh"
fi

EXTRACT_DIR="$WORK_DIR/extracted"
PNG_DIR="$WORK_DIR/png"
rm -rf "$EXTRACT_DIR" "$PNG_DIR"
mkdir -p "$EXTRACT_DIR" "$PNG_DIR" "$DIST_DIR"

extract_or_copy_svg() {
  local input_svg="$1"
  local group="$2"
  local target_svg="$EXTRACT_DIR/$group/${group}.svg"
  local extract_log="$WORK_DIR/.extract_log_${group}.txt"
  local extracted_count=0
  EXTRACT_CMD=("$VENV_PY" "$ROOT_DIR/scripts/extract_sprite_icons.py" --input "$input_svg" --out "$EXTRACT_DIR" --default-group "$group")
  if [[ "$group" == "rd" ]]; then
    EXTRACT_CMD+=(--provider-names)
  fi
  if [[ -n "$PROVIDER_MAP" ]]; then
    EXTRACT_CMD+=(--provider-map "$PROVIDER_MAP")
  fi
  "${EXTRACT_CMD[@]}" >"$extract_log"
  cat "$extract_log"
  if grep -Eq '^extracted [0-9]+ icons to ' "$extract_log"; then
    extracted_count="$(sed -nE 's/^extracted ([0-9]+) icons to .*/\1/p' "$extract_log" | tail -n1)"
  fi
  rm -f "$extract_log"

  if [[ "$extracted_count" -eq 0 ]]; then
    mkdir -p "$(dirname "$target_svg")"
    cp "$input_svg" "$target_svg"
    echo "no extractable symbols found in $(basename "$input_svg"), copied as $target_svg"
  fi
}

copy_icon_alias() {
  local source_dir="$1"
  local preferred="$2"
  local out_name="$3"
  local out_dir="$4"
  local candidate=""
  if [[ -n "$preferred" && -f "$source_dir/$preferred" ]]; then
    candidate="$source_dir/$preferred"
  else
    candidate="$(find "$source_dir" -maxdepth 1 -type f -name '*.png' | sort | head -n1 || true)"
  fi
  if [[ -n "$candidate" ]]; then
    cp "$candidate" "$out_dir/$out_name"
    echo "icon alias: $(basename "$candidate") -> $out_dir/$out_name"
  fi
}

if [[ -n "$INPUT_SVG" ]]; then
  group="$(basename "$INPUT_SVG")"
  group="${group%-pin-sprite.svg}"
  if [[ "$group" == "$(basename "$INPUT_SVG")" ]]; then
    group="fallback"
  fi
  extract_or_copy_svg "$INPUT_SVG" "$group"
else
  shopt -s nullglob
  found=0
  for svg in "$SOURCE_DIR"/*-pin-sprite.svg; do
    found=1
    group="$(basename "$svg")"
    group="${group%-pin-sprite.svg}"
    extract_or_copy_svg "$svg" "$group"
  done
  shopt -u nullglob
  if [[ "$found" -eq 0 ]]; then
    echo "Keine *-pin-sprite.svg in $SOURCE_DIR gefunden." >&2
    exit 2
  fi
fi

"$VENV_PY" "$ROOT_DIR/scripts/convert_sprite_svgs.py" --source "$EXTRACT_DIR" --out "$PNG_DIR"

COMBINED_DIR="$PNG_DIR/oe5ith-markers"
mkdir -p "$COMBINED_DIR"

for group in rd nef nah brd fallback; do
  if [[ -d "$PNG_DIR/$group" ]]; then
    find "$PNG_DIR/$group" -maxdepth 1 -type f -name '*.png' | while read -r icon; do
      base="$(basename "$icon" .png)"
      if [[ ( "$group" == "brd" || "$group" == "fallback" ) && "$base" == "$group" ]]; then
        # In diesen Gruppen ist `<group>-pin` der einzige benötigte Key.
        # Das zusätzliche `<group>-<group>` wäre rein redundant.
        continue
      fi
      cp "$icon" "$COMBINED_DIR/${group}-${base}.png"
    done
  fi
done

copy_icon_alias "$PNG_DIR/brd" "brd.png" "brd-pin.png" "$COMBINED_DIR"
copy_icon_alias "$PNG_DIR/fallback" "fallback.png" "fallback-pin.png" "$COMBINED_DIR"

"$VENV_PY" "$ROOT_DIR/scripts/build_sprites.py" --source "$PNG_DIR" --out "$DIST_DIR"

echo "Done. Sprites written to: $DIST_DIR"
