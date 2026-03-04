# PMTiles Builder + Style Generator (Bundle)

Dieses Archiv enthält zwei Python-Skripte:

1) `geojson_to_pmtiles.py`
   - baut aus vielen GeoJSON-Dateien eine PMTiles-Datei (jede Datei -> eigener source-layer)
   - optional: baut pro Top-Level-Ordner unterhalb des Root-Verzeichnisses eine eigene PMTiles (`--split-top-folders`)
   - kann ein Manifest schreiben (für den Style-Generator)

2) `generate_style_from_manifest_v3.py`
   - erzeugt ein MapLibre `style.json`, das ALLE source-layer aus dem Manifest enthält
   - Linien-Styling via `linien.json` (match auf `properties.LINIE`)
   - Polygon-Farbzuordnung via `color_mapping.json` (match auf `properties.name`)
   - optional: Report, der prüft ob alle `LINIE`/`name` Werte gemappt sind

## Voraussetzungen

- Python 3.9+
- `tippecanoe` im PATH (für den PMTiles-Build)

## 1) Eine einzelne PMTiles aus ALLEN GeoJSONs bauen

```bash
python3 geojson_to_pmtiles.py \
  --root "/pfad/zu/deinem/geojson-root" \
  --out  "/pfad/out/alles.pmtiles" \
  --write-manifest "/pfad/out/alles.manifest.json"
```

## 2) Pro Top-Level-Ordner eine eigene PMTiles bauen (Themen-Split)

```bash
python3 geojson_to_pmtiles.py \
  --root "/pfad/zu/deinem/geojson-root" \
  --out  "/pfad/out_pmtiles" \
  --split-top-folders \
  --write-manifest "/pfad/out_pmtiles/manifests" \
  --extra -z 14
```

Ergebnis (Beispiele):
- `/pfad/out_pmtiles/gemeinden.pmtiles`
- `/pfad/out_pmtiles/rd_dienststellen.pmtiles`
- `/pfad/out_pmtiles/strassen.pmtiles`
- ...

und je eine passende Manifest-Datei:
- `/pfad/out_pmtiles/manifests/gemeinden.manifest.json`
- ...

## 3) Style JSON aus Manifest + linien.json + color_mapping.json erzeugen

```bash
python3 generate_style_from_manifest_v3.py \
  --manifest "/pfad/out_pmtiles/manifests/strassen.manifest.json" \
  --pmtiles-url "pmtiles://https://tiles.example.at/pmtiles/strassen.pmtiles" \
  --out-style "/pfad/out_pmtiles/styles/strassen.style.json" \
  --linien-json "/pfad/geojsonstyle/linien.json" \
  --color-mapping "/pfad/geojsonstyle/color_mapping.json" \
  --name-prop "name" \
  --report "/pfad/out_pmtiles/styles/strassen.style.report.json" \
  --report-sample-limit 0
```

### Hinweise

- MapLibre-Expressions brauchen syntaktisch immer einen Fallback. In diesem Generator ist der Fallback so gewählt,
  dass er praktisch nichts zeichnet (z.B. line-width 0).
- Der Report ist die "QA-Schicht": er zeigt dir fehlende `LINIE` oder `name` Werte, falls etwas nicht gemappt ist.

## Optional: Palette

`color_mapping.json` mappt Keys -> Index (1..6). Die tatsächlichen Farben kommen aus einer Palette.
Im Skript ist eine Default-Palette drin. Wenn du deine echte Palette als JSON hast, kannst du sie mitgeben:

- als Liste: `["#hex1", "#hex2", ...]` (Index 1 = Element 0)
- oder als Dict: `{"1":"#hex", "2":"#hex", ...}`

```bash
python3 generate_style_from_manifest_v3.py ... --palette-json "/pfad/palette.json"
```
