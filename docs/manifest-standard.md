# Manifest-Standard für Karten-Overlays

Dieses Dokument beschreibt die Struktur der `manifest.json`, die als standardisierte Schnittstelle zwischen der Build-Pipeline und externen Verarbeitungs-Skripten dient.

## Zielsetzung
Das Manifest ermöglicht es automatisierten Systemen (z.B. Deployment-Skripten, API-Gateways), alle Bestandteile eines Karten-Builds (PMTiles, Styles, Sprites) ohne manuelle Konfiguration zu identifizieren.

## Pfad
Die Datei befindet sich nach einem erfolgreichen Build unter:
`dist/manifest.json`

## Struktur

```json
{
  "project": "Name des Projekts",
  "generated_at": "ISO-Timestamp (optional)",
  "overlays": [
    {
      "id": "eindeutiger-layer-id",
      "name": "Anzeigename des Layers",
      "style_path": "relativer/pfad/zu/style.json",
      "pmtiles_path": "relativer/pfad/zu/data.pmtiles"
    }
  ],
  "resources": {
    "sprites": [
      {
        "id": "sprite-name",
        "svg_path": "pfad/zu/quell/svg"
      }
    ],
    "fonts": [
      "Name-der-Schriftart"
    ]
  }
}
```

### Felder im Detail

*   **`overlays`**: Eine Liste aller verfügbaren Karten-Layer.
    *   `style_path`: Pfad zur Mapbox GL Style JSON (relativ zum Projekt-Root).
    *   `pmtiles_path`: Pfad zur Datendatei (relativ zum Projekt-Root).
*   **`resources`**: Gemeinsame Ressourcen, die von mehreren Styles genutzt werden können.
    *   `sprites`: Listet alle Quell-Vektorgrafiken auf, aus denen das Sprite-Sheet generiert wird.
    *   `fonts`: Listet die benötigten Schriftfamilien auf (wichtig für die Font-Server-Bereitstellung).

## Implementierung in neuen Projekten
1.  Füge `scripts/generate_manifest.py` zum Projekt hinzu.
2.  Stelle sicher, dass das Script am Ende des Build-Prozesses aufgerufen wird.
3.  Pfade im Manifest sollten immer **relativ zum Repository-Root** angegeben werden, um Portabilität zu gewährleisten.
