#!/usr/bin/env python3
"""Extract icon-only SVGs (plus metadata) from a composite preview SVG.

The script is intended for SVG sheets that contain:
- <defs> with reusable symbols/patterns
- top-level <g> blocks that use <use href="#..."></use>
- optional label/subtitle text that should NOT be part of final sprite icons
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def qname(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


def slugify(value: str) -> str:
    slug = value.lower()
    slug = slug.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "icon"




PROVIDER_PRESET = {
    "örk": {"group": "rd", "name": "oerk"},
    "brk": {"group": "rd", "name": "brk"},
    "asb": {"group": "rd", "name": "asb"},
    "gk": {"group": "rd", "name": "gk"},
    "mhd": {"group": "rd", "name": "mhd"},
    "ims": {"group": "rd", "name": "ims"},
    "stadler": {"group": "rd", "name": "stadler"},
    "juh": {"group": "rd", "name": "juh"},
    "ma70": {"group": "rd", "name": "ma70"},
}


def normalize_label(value: str) -> str:
    return value.strip().lower()


def resolve_provider_target(label: str, provider_map: Dict[str, Dict[str, str]], enforce: bool, default_group: str) -> tuple[str, str]:
    key = normalize_label(label)
    if key in provider_map:
        return provider_map[key].get("group", default_group), provider_map[key].get("name", slugify(label))
    if enforce:
        return default_group, slugify(label)
    return default_group, slugify(label)


def parse_style_vars(style_text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in style_text.split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key.startswith("--") and value:
            result[key] = value
    return result


def get_text_content(node: ET.Element) -> str:
    return "".join(node.itertext()).strip()


def first_label_text(group: ET.Element) -> str:
    for text_node in group.findall(qname("text")):
        classes = text_node.get("class", "")
        if "label" in classes:
            text = get_text_content(text_node)
            if text:
                return text
    for text_node in group.findall(qname("text")):
        text = get_text_content(text_node)
        if text:
            return text
    return ""


def href_of_use(group: ET.Element) -> str:
    use = group.find(qname("use"))
    if use is None:
        return ""
    href = use.get("href") or use.get(f"{{{XLINK_NS}}}href") or ""
    return href


def build_icon_svg(root: ET.Element, defs: ET.Element | None, group: ET.Element) -> ET.ElementTree:
    out_root = ET.Element(qname("svg"), {
        "xmlns": SVG_NS,
        "width": "64",
        "height": "72",
        "viewBox": "0 0 64 72",
    })

    if defs is not None:
        out_root.append(copy.deepcopy(defs))

    icon_group = ET.Element(qname("g"))
    if group.get("style"):
        icon_group.set("style", group.get("style", ""))

    use = group.find(qname("use"))
    if use is not None:
        icon_group.append(copy.deepcopy(use))

    out_root.append(icon_group)
    return ET.ElementTree(out_root)


def extract_icons(
    input_svg: Path,
    out_dir: Path,
    provider_map: Dict[str, Dict[str, str]],
    enforce_provider_names: bool,
    default_group: str,
) -> int:
    tree = ET.parse(input_svg)
    root = tree.getroot()
    defs = root.find(qname("defs"))

    out_dir.mkdir(parents=True, exist_ok=True)
    metadata: List[Dict[str, str]] = []

    index = 1
    for child in list(root):
        if child.tag != qname("g"):
            continue
        href = href_of_use(child)
        if not href:
            continue

        label = first_label_text(child) or f"icon-{index}"
        group, icon_name = resolve_provider_target(label, provider_map, enforce_provider_names, default_group)
        rel_file = Path(group) / f"{icon_name}.svg"
        output_svg = out_dir / rel_file
        output_svg.parent.mkdir(parents=True, exist_ok=True)

        icon_tree = build_icon_svg(root, defs, child)
        icon_tree.write(output_svg, encoding="utf-8", xml_declaration=True)

        styles = parse_style_vars(child.get("style", ""))
        metadata.append({
            "group": group,
            "name": icon_name,
            "file": rel_file.as_posix(),
            "label": label,
            "symbol": href,
            "fillVar": styles.get("--fill", ""),
            "iconVar": styles.get("--icon", ""),
        })
        index += 1

    manifest_path = out_dir / "icons.manifest.json"
    manifest_path.write_text(json.dumps({"version": 1, "icons": metadata}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"extracted {len(metadata)} icons to {out_dir}")
    print(f"wrote metadata: {manifest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract icon-only SVGs from a composite preview SVG.")
    parser.add_argument("--input", required=True, help="Path to composite SVG file.")
    parser.add_argument("--out", default="assets/sprites/extracted", help="Directory for extracted icon SVGs.")
    parser.add_argument("--provider-map", default="", help="Optional JSON file mapping labels to {group,name}.")
    parser.add_argument("--provider-names", action="store_true", help="Use provider-based grouped target names (rd/nef/nah/brd/fallback).")
    parser.add_argument("--default-group", default="fallback", help="Default output group for labels not present in provider map.")
    args = parser.parse_args()

    input_svg = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    if not input_svg.exists():
        raise SystemExit(f"input SVG not found: {input_svg}")

    provider_map = dict(PROVIDER_PRESET) if args.provider_names else {}
    if args.provider_map:
        map_path = Path(args.provider_map).expanduser().resolve()
        payload = json.loads(map_path.read_text(encoding="utf-8"))
        provider_map.update({str(k).strip().lower(): v for k, v in payload.items()})

    return extract_icons(input_svg, out_dir, provider_map, args.provider_names, args.default_group)


if __name__ == "__main__":
    raise SystemExit(main())
