# Sprite assets

Lege hier die Sprite-Quellen für `rd`, `nah`, `nef` und `brd` ab
(z. B. `*.png` und ggf. generierte `sprite.json`/`sprite.png` Varianten).

Empfohlene Quellstruktur:
- `assets/sprites/rd/*.png`
- `assets/sprites/nah/*.png`
- `assets/sprites/nef/*.png`
- `assets/sprites/brd/*.png`

Sprite-Build ausführen:
```bash
python3 scripts/build_sprites.py --source assets/sprites --out dist/assets/sprites
```

Dieser Ordner ist die zentrale Quelle für die spätere Bereitstellung über
`/assets/sprites/...` im Hosted-Setup.


SVG-Konvertierung (SVG -> PNG):
```bash
python3 scripts/convert_sprite_svgs.py --source assets/sprites --out assets/sprites/png
```

Danach Sprite-Build ausführen:
```bash
python3 scripts/build_sprites.py --source assets/sprites/png --out dist/assets/sprites
```
