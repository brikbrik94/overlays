# PMTiles Style Assets – benötigte Dateien & Sprite-Vorschlag

## 1) Status im aktuellen Repo

Die folgenden Marker-/Glyph-/Sprite-Dateien sind in **diesem Repository aktuell nicht enthalten**.
Die unten genannten Pfade/URLs sind daher als Zielstruktur bzw. Referenz zu verstehen, nicht als bereits commitete Assets.

Fehlend im aktuellen Stand sind insbesondere:

- einzelne Marker-SVGs (z. B. `rd-pin`, `nah-pin`, `nef-pin`, `brd-pin`, `fallback-pin`)
- ein fertiger Sprite-Atlas (`.png`, `@2x.png`, `.json`)
- Glyph-PBF-Dateien für Textlabels
- ein lokaler Ablageort im Repo war bisher nicht vorhanden; dieser liegt jetzt unter `assets/fonts/`

## 2) Für externe Style-JSONs benötigte Runtime-Assets

Damit die erzeugten Styles direkt von `tiles.oe5ith.at` geladen werden können, werden serverseitig zusätzlich benötigt:

1. **Sprite-Atlas** (MapLibre-Standard)

   - `https://tiles.oe5ith.at/assets/sprites/oe5ith-markers.png`
   - `https://tiles.oe5ith.at/assets/sprites/oe5ith-markers@2x.png`
   - `https://tiles.oe5ith.at/assets/sprites/oe5ith-markers.json`

2. **Glyphs (PBF)** für Textlabels

   - `https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf`

3. optional: **Fallback-Styles** je Ordner
   - z. B. `/styles/rd-dienststellen.style.json`

## 3) Vorschlag: Pin-SVGs zu einem gemeinsamen Sprite zusammenfassen

### Ziel

Statt pro Kategorie getrennte SVG-Logik zu fahren, ein einheitlicher MapLibre-Sprite-Atlas mit klaren IDs:

- `rd-pin`
- `nah-pin`
- `nef-pin`
- `brd-pin`
- `fallback-pin`

### Empfohlener Workflow

1. SVGs normalisieren (ViewBox, Padding, visuelle Baseline)
2. Atlas bauen (`.png`, `@2x.png`, `.json`)
3. IDs stabil halten (keine Umbenennungen ohne Migration)
4. Styles nur über `icon-image` referenzieren

### Tooling-Optionen

- `@jutaz/spritezero` / `spritezero-cli`
- alternativ Build-Schritt mit eigenem Node-Script

## 4) Datenstruktur für die ausgelagerten PMTiles

Empfohlene Zielstruktur auf `tiles.oe5ith.at`:

- `/pmtiles/Bezirke.pmtiles`
- `/pmtiles/Gemeinden.pmtiles`
- `/pmtiles/Leitstellen-Bereiche.pmtiles`
- `/pmtiles/NAH-Stützpunkte.pmtiles`
- `/pmtiles/RD-Dienststellen.pmtiles`
- `/pmtiles/Sonstiges.pmtiles`
- `/pmtiles/Straßen-Autobahnen.pmtiles`
- `/pmtiles/Straßen-Bundesstraßen.pmtiles`
- `/pmtiles/Zonen.pmtiles`

Die einzelnen ursprünglichen Dateien bleiben als `source-layer` in der jeweiligen Ordner-PMTiles enthalten.
