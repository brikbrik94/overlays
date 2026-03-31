#!/usr/bin/env python3
"""Local test server for previewing generated overlay styles with MapLibre.

Usage example:
  python3 test_overlay_server.py --bundle-dir dist --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

VIEWER_DIR = Path(__file__).resolve().parent / "viewer"
DEFAULT_BUNDLE_DIR = Path(__file__).resolve().parent / "dist"
REPO_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


class OverlayRequestHandler(BaseHTTPRequestHandler):
    server_version = "OverlayTestServer/1.0"

    def do_HEAD(self) -> None:
        self.handle_request(head_only=True)

    def do_GET(self) -> None:
        self.handle_request(head_only=False)

    def handle_request(self, head_only: bool) -> None:
        self.head_only = head_only
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self.serve_file(VIEWER_DIR / "index.html")
        if path == "/viewer/app.js":
            return self.serve_file(VIEWER_DIR / "app.js")
        if path == "/viewer/styles.css":
            return self.serve_file(VIEWER_DIR / "styles.css")
        if path == "/favicon.ico":
            return self.send_response_no_content()
        if path == "/api/overlays":
            return self.serve_overlays()
        if path.startswith("/assets/"):
            relative = unquote(path.removeprefix("/assets/"))
            return self.serve_assets_file(relative)
        if path == "/api/style":
            query = parse_qs(parsed.query)
            style_file = query.get("style", [None])[0]
            return self.serve_style(style_file)
        if path.startswith("/bundle/"):
            relative = unquote(path.removeprefix("/bundle/"))
            return self.serve_bundle_file(relative)

        self.send_error(HTTPStatus.NOT_FOUND, "Route nicht gefunden")

    def send_response_no_content(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    @property
    def bundle_dir(self) -> Path:
        return self.server.bundle_dir  # type: ignore[attr-defined]

    def read_index(self) -> List[Dict[str, Any]]:
        index_path = self.bundle_dir / "styles" / "index.json"
        if not index_path.exists():
            return []
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("styles/index.json muss eine Liste sein")
        return data

    def serve_overlays(self) -> None:
        try:
            entries = self.read_index()
        except Exception as exc:
            return self.send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        overlays = []
        for entry in entries:
            style_file = str(entry.get("styleFile", ""))
            overlays.append({
                "id": style_file,
                "label": entry.get("folder", style_file),
                "styleFile": style_file,
                "styleApiUrl": f"/api/style?style={style_file}",
                "pmtilesFile": entry.get("pmtilesFile"),
                "sourceLayerCount": entry.get("sourceLayerCount", 0),
            })

        self.send_json({
            "bundleDir": str(self.bundle_dir),
            "count": len(overlays),
            "overlays": overlays,
        })

    def serve_style(self, style_file: Optional[str]) -> None:
        if not style_file:
            return self.send_json({"error": "Query-Parameter 'style' fehlt."}, status=HTTPStatus.BAD_REQUEST)

        try:
            style_path = self.safe_bundle_path(style_file)
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        if not style_path.exists():
            return self.send_json({"error": f"Style nicht gefunden: {style_file}"}, status=HTTPStatus.NOT_FOUND)

        try:
            style = json.loads(style_path.read_text(encoding="utf-8"))
            style = self.sanitize_rd_style(style, style_file)
            style = self.rewrite_style_for_local_bundle(style, style_file)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        self.send_json(style)

    def sanitize_rd_style(self, style: Dict[str, Any], style_file: str) -> Dict[str, Any]:
        if not style_file.endswith("rd-dienststellen.style.json"):
            return style

        layers = style.get("layers")
        if not isinstance(layers, list):
            return style

        seen_ids = set()
        normalized_layers = []
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            layer_id = str(layer.get("id", ""))
            if layer_id and layer_id in seen_ids:
                continue
            if layer_id:
                seen_ids.add(layer_id)

            if layer.get("type") == "symbol" and layer.get("source") == "folder":
                layout = layer.setdefault("layout", {})
                if isinstance(layout, dict):
                    layout["icon-image"] = ["coalesce", ["get", "pin"], "fallback-pin"]
                    layout["icon-size"] = ["interpolate", ["linear"], ["zoom"], 6, 0.35, 12, 0.65]
                    layout["icon-allow-overlap"] = True
                    layout["icon-ignore-placement"] = True
                    for key in ["text-field", "text-size", "text-font", "text-offset", "text-anchor", "text-optional"]:
                        layout.pop(key, None)
            normalized_layers.append(layer)

        style["layers"] = normalized_layers
        return style

    def rewrite_style_for_local_bundle(self, style: Dict[str, Any], style_file: str) -> Dict[str, Any]:
        entries = self.read_index()
        entry = next((item for item in entries if item.get("styleFile") == style_file), None)
        pmtiles_file = None if entry is None else entry.get("pmtilesFile")
        forwarded_proto = self.headers.get("X-Forwarded-Proto", "http")
        host = self.headers.get("Host", f"{self.server.server_address[0]}:{self.server.server_address[1]}")

        if pmtiles_file:
            local_pmtiles_url = f"pmtiles://{forwarded_proto}://{host}/bundle/{pmtiles_file}"
            for source in style.get("sources", {}).values():
                if source.get("type") == "vector":
                    source["url"] = local_pmtiles_url

        style.setdefault("metadata", {})["localTestServer"] = {
            "styleFile": style_file,
            "pmtilesFile": pmtiles_file,
        }
        return style

    def serve_assets_file(self, relative: str) -> None:
        try:
            asset_path = self.safe_assets_path(relative)
        except ValueError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        self.serve_file(asset_path)

    def serve_bundle_file(self, relative: str) -> None:
        try:
            bundle_path = self.safe_bundle_path(relative)
        except ValueError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        self.serve_file(bundle_path)

    def safe_assets_path(self, relative: str) -> Path:
        roots = [
            (self.bundle_dir / "assets").resolve(),
            REPO_ASSETS_DIR.resolve(),
        ]
        for assets_root in roots:
            candidate = (assets_root / relative).resolve()
            if assets_root == candidate or assets_root in candidate.parents:
                if candidate.exists():
                    return candidate
        raise ValueError("Ungültiger Pfad außerhalb des Assets-Verzeichnisses")

    def safe_bundle_path(self, relative: str) -> Path:
        candidate = (self.bundle_dir / relative).resolve()
        bundle_root = self.bundle_dir.resolve()
        if bundle_root == candidate or bundle_root in candidate.parents:
            return candidate
        raise ValueError("Ungültiger Pfad außerhalb des Bundle-Verzeichnisses")

    def parse_range_header(self, file_size: int) -> Optional[Tuple[int, int]]:
        header = self.headers.get("Range")
        if not header:
            return None
        if not header.startswith("bytes="):
            raise ValueError("Nur Byte-Ranges werden unterstützt")

        spec = header.removeprefix("bytes=").strip()
        if "," in spec:
            raise ValueError("Mehrfach-Ranges werden nicht unterstützt")

        start_text, end_text = spec.split("-", 1)
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError("Ungültiger Suffix-Range")
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        else:
            start = int(start_text)
            end = file_size - 1 if not end_text else int(end_text)

        if start < 0 or end < start or start >= file_size:
            raise ValueError("Range außerhalb der Datei")

        return start, min(end, file_size - 1)

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, f"Datei nicht gefunden: {path}")
            return

        file_size = path.stat().st_size
        try:
            byte_range = self.parse_range_header(file_size)
        except ValueError:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return

        mime_type, _ = mimetypes.guess_type(path.name)
        start = 0 if byte_range is None else byte_range[0]
        end = file_size - 1 if byte_range is None else byte_range[1]
        length = end - start + 1
        status = HTTPStatus.PARTIAL_CONTENT if byte_range else HTTPStatus.OK

        self.send_response(status)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()

        if getattr(self, "head_only", False):
            return

        with path.open("rb") as handle:
            handle.seek(start)
            self.wfile.write(handle.read(length))

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if not getattr(self, "head_only", False):
            self.wfile.write(raw)


class OverlayTestServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], bundle_dir: Path):
        super().__init__(server_address, OverlayRequestHandler)
        self.bundle_dir = bundle_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local viewer for generated overlay bundles.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    parser.add_argument("--bundle-dir", default=str(DEFAULT_BUNDLE_DIR), help="Directory containing styles/, manifests/ and pmtiles/.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle_dir = Path(args.bundle_dir).expanduser().resolve()
    if not bundle_dir.exists():
        raise SystemExit(f"Bundle-Verzeichnis existiert nicht: {bundle_dir}")

    server = OverlayTestServer((args.host, args.port), bundle_dir)
    print(f"Viewer:   http://{args.host}:{args.port}/")
    print(f"Bundle:   {bundle_dir}")
    print("Beenden:  Ctrl+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
