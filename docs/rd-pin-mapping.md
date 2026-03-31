# RD Pin Mapping (RD-Dienststellen)

Diese Doku beschreibt, wie das Feld `pin` für RD-Dienststellen erzeugt wird.

## Wo passiert die Zuordnung?

Die Zuordnung passiert im Build-Prozess in `build_hosted_overlays.py`:

1. `derive_rd_pin(properties)` berechnet den finalen Pin-Namen.
2. `build_rd_enriched_geojson(src, dst)` schreibt den Pin in jedes Feature (`properties.pin`).
3. Beim Bundle `rd-dienststellen` werden die angereicherten GeoJSON-Dateien temporär erzeugt und für tippecanoe verwendet.

Das Style selbst nutzt danach nur noch:

```json
["coalesce", ["get", "pin"], "fallback-pin"]
```

## Entscheidungslogik

### 1) Fahrzeug-/Diensttyp

- **BRD**: `emergency == mountain_rescue` → `brd-pin`
- Sonst nur weiter, wenn `emergency == ambulance_station`
- **NEF**: wenn `ambulance_station:emergency_doctor` truthy
- **RD**: sonst wenn `ambulance_station:patient_transport` truthy  
  (Fallback: bei `emergency=ambulance_station` ohne NEF-Flag ebenfalls RD, damit Datensätze ohne konsistent gepflegtes `patient_transport` weiterhin korrekt gerendert werden)
- Wenn weder NEF noch RD zutrifft → `fallback-pin`

> Wenn NEF und RD beide zutreffen, gewinnt **NEF**.

### 2) Organisations-Mapping

Primär wird `brand:short` verwendet:

- `BRK` → `brk`
- `ÖRK`/`OERK` → `oerk`
- `ASB` → `asb`
- `MHD` → `mhd`
- `JUH` → `juh`
- `GK` → `gk`
- `MA70` → `ma70`
- `IMS` → `ims`
- `STADLER` → `stadler`

Wenn `brand:short` fehlt oder nicht gemappt werden kann, wird auf Textsuche in
`brand`, `operator`, `name`, `short_name` zurückgefallen (z. B. `Rettungsdienst Stadler`, `Bayerisches Rotes Kreuz`, `Malteser`, …).

Aus Typ + Suffix wird der finale Pin:

- RD: `rd-<suffix>` (z. B. `rd-brk`)
- NEF: `nef-<suffix>` (z. B. `nef-brk`)

Wenn kein Suffix gefunden wird: `fallback-pin`.

## Neue Pins hinzufügen

1. Sprite-Assets ergänzen (z. B. `rd-neuerdienst.png` / `nef-neuerdienst.png`) und Sprite-Pipeline laufen lassen.
2. `derive_rd_pin` Mapping erweitern:
   - `brand:short`-Mapping ergänzen **oder**
   - Fallback-Textmatch ergänzen.
3. PMTiles neu bauen (`python3 build_hosted_overlays.py --clean`).
4. Im Viewer prüfen, ob `properties.pin` korrekt gesetzt ist.

## Truthy-Regel

Für Felder wie `ambulance_station:emergency_doctor` gelten als truthy:

- bool: `true`
- Zahl: ungleich `0`
- String: `1`, `true`, `yes`, `y`, `ja` (case-insensitive)
