# Lokale Glyph-Assets

Lege hier deine MapLibre-Glyph-PBF-Dateien ab.

Erwartete Struktur:

```text
assets/fonts/
  <Fontstack>/
    0-255.pbf
    256-511.pbf
    ...
```

Beispiel:

```text
assets/fonts/
  Segoe UI Regular/
    0-255.pbf
    256-511.pbf
  Arial Unicode MS Regular/
    0-255.pbf
    256-511.pbf
```

Der lokale Testserver liefert diesen Ordner unter `/assets/fonts/...` aus, sodass du die Dateien für lokale Viewer-Tests direkt hier hinein kopieren kannst.
