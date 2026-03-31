# NAH Pin Mapping (NAH-Stützpunkte)

Diese Doku beschreibt, wie das Feld `pin` für NAH-Stützpunkte erzeugt wird.

## Überblick

Beim Build wird jede NAH-GeoJSON-Datei vor Tippecanoe angereichert:

1. `derive_nah_pin(properties)` berechnet den finalen Pin-Namen.
2. `build_nah_enriched_geojson(src, dst)` schreibt den Pin in jedes Feature (`properties.pin`).
3. Der Style nutzt anschließend:

```json
["coalesce", ["get", "pin"], "nah-pin"]
```

Dadurch greifen provider-spezifische Sprite-Icons automatisch für Punktdaten,
während Polygone (z. B. `NAH-Zonen-Österreich.geojson`) weiterhin als Fill/Line
gezeichnet werden.

## Mapping-Logik

`derive_nah_pin` prüft Textfelder wie `brand`, `operator`, `name`,
`short_name`, `description`, `alt_name` (normalisiert Umlaute) und mappt auf:

- `nah-adac-luftrettung`
- `nah-drf-luftrettung`
- `nah-oeamtc-flugrettung`
- `nah-martin-flugrettung`
- `nah-schenk-air`
- `nah-ara-flugrettung`
- `nah-wucher-helicopter`
- `nah-shs-schider-helicopter-service`
- `nah-bundesministerium-des-inneren`

Wenn kein Treffer gefunden wird, wird `nah-pin` als Fallback gesetzt.
