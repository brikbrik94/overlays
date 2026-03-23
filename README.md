# PMTiles Builder + Style Generator

Dieses Repository ist jetzt auf einen **deploybaren Export-Workflow** für deine GeoJSON-Ordnerstruktur ausgerichtet.

Ziel: Aus `geojson/**` sollen automatisch

- fertige `.pmtiles`-Dateien,
- passende `manifest.json`-Dateien,
- hostbare MapLibre-`style.json`-Dateien,
- und eine `styles/index.json`

entstehen, damit du das Bundle direkt auf einem Server wie `tiles.oe5ith.at` ausliefern kannst.

## Enthaltene Skripte

### 1) `build_hosted_overlays.py`

Der neue Haupt-Workflow für den produktiven Export.

Er scannt das GeoJSON-Root rekursiv und behandelt **jeden Ordner, der direkt `.geojson`-Dateien enthält**, als eigenes Overlay-Bundle.

Beispiele aus diesem Repo:

- `geojson/Gemeinden` → `pmtiles/Gemeinden.pmtiles`
- `geojson/RD-Dienststellen` → `pmtiles/RD-Dienststellen.pmtiles`
- `geojson/Straßen/Autobahnen` → `pmtiles/Straßen/Autobahnen.pmtiles`
- `geojson/Anfahrtszeit/Linz` → `pmtiles/Anfahrtszeit/Linz.pmtiles`

Pro Bundle erzeugt das Skript:

- `pmtiles/<Ordner>.pmtiles`
- `manifests/<Ordner>.manifest.json`
- `styles/<slug>.style.json`

Zusätzlich wird ein globales `styles/index.json` geschrieben.

#### Beispiel: nur Styles + Manifeste erzeugen

Wenn `tippecanoe` lokal noch nicht installiert ist:

```bash
python3 build_hosted_overlays.py \
  --root geojson \
  --out dist \
  --skip-pmtiles
```

#### Beispiel: komplettes Hosting-Bundle erzeugen

```bash
python3 build_hosted_overlays.py \
  --root geojson \
  --out dist \
  --base-url https://tiles.example.at
```

#### Beispiel: mit zusätzlichen `tippecanoe`-Parametern

```bash
python3 build_hosted_overlays.py \
  --root geojson \
  --out dist \
  --base-url https://tiles.example.at \
  --extra -z 14 --coalesce-densest-as-needed
```

### 2) `geojson_to_pmtiles.py`

Low-Level-Helfer, falls du gezielt aus vielen GeoJSON-Dateien eine oder mehrere PMTiles bauen willst.

### 3) `generate_style_from_manifest_v3.py`

Spezial-Generator für Manifest-basierte Styles mit `linien.json` / `color_mapping.json`.
Das Skript bleibt im Repo, ist aber **nicht mehr der einfachste Hauptweg** für dein aktuelles Hosting-Ziel.

## Zielstruktur im Output

Nach einem Lauf mit `--out dist` sieht die Struktur sinngemäß so aus:

```text
dist/
  pmtiles/
    Gemeinden.pmtiles
    RD-Dienststellen.pmtiles
    Straßen/
      Autobahnen.pmtiles
  manifests/
    Gemeinden.manifest.json
    Straßen/
      Autobahnen.manifest.json
  styles/
    gemeinden.style.json
    rd-dienststellen.style.json
    strassen-autobahnen.style.json
    index.json
```

## Styling / Hosting

Die erzeugten Styles orientieren sich an der bereits vorhandenen dunklen CI-Optik:

- dunkler Hintergrund
- blauer Akzent (`#3b82f6`)
- Polygon-Fill + Outline
- Linien mit zoomabhängiger Breite
- Punktlayer als Circle oder Symbol-Layer
- `RD-Dienststellen` und `NAH-Stützpunkte` verwenden Sprite-Icons, wenn du die Sprite-Dateien serverseitig bereitstellst

Standardmäßig referenzieren die Styles:

- Sprite: `https://tiles.oe5ith.at/assets/sprites/oe5ith-markers`
- Glyphs: `https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf`

Diese URLs kannst du per CLI überschreiben.


## Lokaler Test-Viewer

Zusätzlich gibt es jetzt einen kleinen Python-Testserver mit MapLibre-Viewer:

- Server: `test_overlay_server.py`
- Viewer-Dateien: `viewer/index.html`, `viewer/app.js`, `viewer/styles.css`

Der Viewer lädt:

- eine OSM-Basiskarte,
- die Overlay-Liste aus `styles/index.json`,
- und das ausgewählte Overlay per Dropdown.

### Beispielablauf

Zuerst ein lokales Bundle erzeugen:

```bash
python3 build_hosted_overlays.py \
  --root geojson \
  --out dist \
  --base-url http://127.0.0.1:8000 \
  --skip-pmtiles
```

Danach den Testserver starten:

```bash
python3 test_overlay_server.py --bundle-dir dist --host 127.0.0.1 --port 8000
```

Dann im Browser öffnen:

- `http://127.0.0.1:8000/`

### Was der Server macht

- liefert die Viewer-Seite aus
- liefert `/api/overlays` aus `styles/index.json`
- liefert `/api/style?style=...` für das ausgewählte Style-JSON
- schreibt PMTiles-Source-URLs für den lokalen Test auf `/bundle/...` um
- unterstützt HTTP Byte-Range-Requests für PMTiles-Dateien
- serviert das Build-Verzeichnis unter `/bundle/`
- serviert lokale Runtime-Assets unter `/assets/` (z. B. `assets/fonts/...`)

Damit kannst du lokal sehr schnell prüfen, ob dein Export und die Layer-Struktur so funktionieren, wie du es später auf dem Server hosten willst.

Wenn du eigene Glyph-PBFs lokal testen willst, lege sie unter `assets/fonts/` ab. Der Testserver liefert diesen Ordner direkt unter `/assets/fonts/...` aus.

## Voraussetzungen

- Python 3.9+
- für echte `.pmtiles`-Builds: `tippecanoe` im `PATH`

## Deployment-Empfehlung

1. `python3 build_hosted_overlays.py --root geojson --out dist --base-url https://dein-server.example`
2. Inhalt von `dist/` auf den Server kopieren.
3. Zusätzlich Sprite- und Glyph-Assets bereitstellen.
4. In deiner Web-App das gewünschte Style-JSON aus `dist/styles/index.json` auswählen.

## Bestehende Referenzdateien

Unter `pmtiles/styles/` liegen weiterhin die bisher erzeugten/zusammengeführten Style-JSONs als Referenz.
Unter `pmtiles/asset-checklist.md` stehen die zusätzlich benötigten Runtime-Assets für produktives Hosting.
