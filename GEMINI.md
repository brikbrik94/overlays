# Projekt-Status: Modulare Overlay-Build-Pipeline

Diese Datei dient als Gedächtnisstütze für den aktuellen Stand der Umstellung auf das modulare Build-System.

## Aktueller Fortschritt
Wir migrieren den monolithischen Build-Prozess von `build_hosted_overlays.py` hin zu einer modularen Struktur unter `scripts/`.

### Implementierte Module
- **PMTiles-Builder:** `scripts/pmtiles_builder.py` übernimmt die Konvertierung von GeoJSON zu PMTiles (inkl. Pin-Logik für RD/NAH und Tippecanoe-Steuerung mit `-r 1` zum Schutz aller Features).
- **Style-Orchestrierung:** `scripts/run_style_build.sh` führt die einzelnen Kategorien-Builder aus.
- **Style-Utils:** `scripts/style_builders/style_utils.py` enthält globale Konstanten (z.B. Font `Noto-Sans-Regular`).
- **Index-Generator:** `scripts/generate_index.py` erstellt die `index.json` für den Viewer.

### Umgestellte Layer (Modular)
1.  **NAH-Stützpunkte (`build_nah.py`):**
    *   Nutzt `manifest.json` zur Unterscheidung von Punkt- und Polygon-Layern.
    *   Stellt nur `alt_name` dar.
    *   Weiße Blase (SDF) wurde auf Wunsch vorerst entfernt.
2.  **RD-Dienststellen (`build_rd.py`):**
    *   Pins für alle Organisationen.
    *   Stellt `alt_name` direkt unter dem Pin dar (weiß mit schwarzem Halo).
    *   Fix: `to-string` Konvertierung für numerische IDs.
3.  **Zonen (`build_zonen.py`):**
    *   Automatisches Einfärben basierend auf `assets/mappings/color_mapping.json`.
    *   Unterstützt Unterordner (z.B. `Zonen/X`).
4.  **Bezirke & Gemeinden (`build_bezirke.py`, `build_gemeinden.py`):**
    *   Polygone mit Labels (Zentroid + Pfad-basiert).
    *   Einheitliche Schriftart `Noto-Sans-Regular`.
5.  **Straßen (`build_strassen.py`):**
    *   Getrennte Styles für Autobahnen (Blau) und Bundesstraßen (Gelb).
    *   Linien-Styles mit Labels (Ref-Shields).
6.  **Leitstellen-Bereiche (`build_leitstellen.py`):**
    *   Automatische Farbpalette für verschiedene Bereiche.
    *   Labels mit Halo zur besseren Lesbarkeit.
7.  **Anfahrtszeiten (`build_anfahrtszeit.py`):**
    *   Farbrampe basierend auf Zeit-Intervallen (Grün -> Rot).
8.  **Sonstiges (`build_sonstiges.py`):**
    *   Styles für Bus- und Tramlinien basierend auf `linien.json` der Website.
    *   Automatische Erkennung von Schnellbussen und Stadtteillinien.
    *   Linien-Labels mit Halo zur besseren Lesbarkeit.

## Wichtige Konfigurationen
- **Schriftart:** Muss zwingend `Noto-Sans-Regular` (mit Bindestrichen) sein.
- **Pfad-Sanitierung:** Alle Layer-IDs und Dateinamen werden in ASCII-Kleinschreibung umgewandelt (ä->ae, etc.).
- **Test-Server:** `test_overlay_server.py` wurde angepasst, um keine Text-Attribute im RD-Style mehr zu filtern.

## Offene Aufgaben (Next Steps)
- [x] **Finaler Cleanup:** Alle veralteten Skripte (`build_hosted_overlays.py`, etc.) wurden in den Ordner `legacy/` verschoben. Die modulare Pipeline ist nun der Standard.

## Build ausführen
```bash
# PMTiles bauen (aus external/geojson-data)
bash scripts/run_pmtiles_build.sh

# Styles und Index bauen
bash scripts/run_style_build.sh
```
