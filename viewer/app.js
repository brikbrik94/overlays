const statusBox = document.getElementById('status-box');
const overlaySelect = document.getElementById('overlay-select');
const reloadButton = document.getElementById('reload-button');
const DEBUG_SPRITES = true;

function setStatus(message, extra) {
  statusBox.textContent = extra ? `${message}\n\n${extra}` : message;
}

const protocol = new pmtiles.Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

const DEFAULT_GLYPHS = 'https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf';
const BASE_OSM_SOURCE = {
  type: 'raster',
  tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
  tileSize: 256,
  attribution: '© OpenStreetMap-Mitwirkende',
  maxzoom: 19,
};
const BASE_OSM_LAYER = {
  id: 'osm',
  type: 'raster',
  source: 'osm',
};

const map = new maplibregl.Map({
  container: 'map',
  center: [13.8, 48.2],
  zoom: 7,
  hash: true,
  style: {
    version: 8,
    glyphs: DEFAULT_GLYPHS,
    sources: {
      osm: BASE_OSM_SOURCE,
    },
    layers: [BASE_OSM_LAYER],
  },
});

map.addControl(new maplibregl.NavigationControl(), 'top-right');

let overlayCatalog = [];
async function fetchOverlayCatalog() {
  const response = await fetch('/api/overlays');
  if (!response.ok) {
    throw new Error(`Overlay-Liste konnte nicht geladen werden (${response.status}).`);
  }
  return response.json();
}

async function fetchOverlayStyle(styleFile) {
  const response = await fetch(`/api/style?style=${encodeURIComponent(styleFile)}`);
  if (!response.ok) {
    throw new Error(`Style konnte nicht geladen werden (${response.status}).`);
  }
  return response.json();
}

function resolveSpriteJsonUrl(spriteBase) {
  const base = `${window.location.origin}/api/style`;
  return new URL(`${spriteBase}.json`, base).toString();
}

async function debugSpriteAvailability(style, styleFile) {
  if (!DEBUG_SPRITES || !style?.sprite) {
    return null;
  }

  const spriteJsonUrl = resolveSpriteJsonUrl(style.sprite);
  const requiredIcons = styleFile.includes('rd-dienststellen')
    ? ['brd-pin', 'fallback-pin']
    : styleFile.includes('nah-stuetzpunkte')
      ? ['fallback-pin']
      : [];

  try {
    const response = await fetch(spriteJsonUrl);
    if (!response.ok) {
      console.warn('[sprite-debug] sprite.json request failed', {
        styleFile,
        spriteBase: style.sprite,
        spriteJsonUrl,
        status: response.status,
      });
      return { ok: false, status: response.status, spriteJsonUrl };
    }

    const payload = await response.json();
    const keys = Object.keys(payload || {});
    const missing = requiredIcons.filter((icon) => !keys.includes(icon));
    console.info('[sprite-debug] sprite.json loaded', {
      styleFile,
      spriteBase: style.sprite,
      spriteJsonUrl,
      iconCount: keys.length,
      requiredIcons,
      missingIcons: missing,
      sampleIcons: keys.slice(0, 12),
    });
    return {
      ok: true,
      spriteJsonUrl,
      iconCount: keys.length,
      missingIcons: missing,
    };
  } catch (error) {
    console.error('[sprite-debug] sprite.json debug failed', {
      styleFile,
      spriteBase: style.sprite,
      spriteJsonUrl,
      error: String(error),
    });
    return { ok: false, spriteJsonUrl, error: String(error) };
  }
}

function populateOverlaySelect(items) {
  overlaySelect.innerHTML = '<option value="">-- kein Overlay --</option>';
  for (const item of items) {
    const option = document.createElement('option');
    option.value = item.styleFile;
    option.textContent = `${item.label} (${item.sourceLayerCount} Layer)`;
    overlaySelect.appendChild(option);
  }
}

function cloneStyleLayer(layer) {
  return JSON.parse(JSON.stringify(layer));
}

function normalizeOverlayLayers(style) {
  const layers = [];

  for (const layer of style.layers || []) {
    if (!layer.source || !style.sources || !style.sources[layer.source]) {
      continue;
    }
    if (layer.type === 'background' || layer.source === 'osm') {
      continue;
    }
    layers.push(cloneStyleLayer(layer));
  }

  return layers;
}

function composeMapStyle(overlayStyle) {
  const mergedStyle = {
    version: 8,
    glyphs: overlayStyle.glyphs || DEFAULT_GLYPHS,
    sources: {
      osm: BASE_OSM_SOURCE,
      ...(overlayStyle.sources || {}),
    },
    layers: [BASE_OSM_LAYER, ...normalizeOverlayLayers(overlayStyle)],
  };
  if (overlayStyle.sprite) {
    mergedStyle.sprite = overlayStyle.sprite;
  }
  return mergedStyle;
}

async function debugOverlayFeatures(style, styleFile) {
  if (!DEBUG_SPRITES || !style?.sources?.folder) {
    return null;
  }

  await new Promise((resolve) => {
    if (map.isStyleLoaded()) {
      resolve();
      return;
    }
    map.once('idle', resolve);
  });

  const sourceLayers = [...new Set((style.layers || [])
    .filter((layer) => layer.source === 'folder' && layer['source-layer'])
    .map((layer) => layer['source-layer']))];

  const counts = {};
  for (const layerName of sourceLayers) {
    try {
      const features = map.querySourceFeatures('folder', { sourceLayer: layerName });
      counts[layerName] = features.length;
    } catch (error) {
      counts[layerName] = `error: ${String(error)}`;
    }
  }

  console.info('[sprite-debug] source feature counts', { styleFile, counts });
  return counts;
}

async function applyOverlay(styleFile) {
  if (!styleFile) {
    map.setStyle({
      version: 8,
      glyphs: DEFAULT_GLYPHS,
      sources: { osm: BASE_OSM_SOURCE },
      layers: [BASE_OSM_LAYER],
    });
    setStatus('Kein Overlay ausgewählt.');
    return;
  }

  const style = await fetchOverlayStyle(styleFile);
  const spriteDebug = await debugSpriteAvailability(style, styleFile);
  map.setStyle(composeMapStyle(style), { diff: false });
  const sourceFeatureCounts = await debugOverlayFeatures(style, styleFile);
  const activeOverlay = style.metadata?.localTestServer || { styleFile };
  setStatus(
    `Overlay geladen: ${style.metadata?.folder || styleFile}`,
    JSON.stringify(
      {
        styleFile,
        sourceCount: Object.keys(style.sources || {}).length,
        layerCount: normalizeOverlayLayers(style).length,
        pmtilesFile: activeOverlay.pmtilesFile || null,
        sprite: style.sprite || null,
        spriteDebug,
        sourceFeatureCounts,
      },
      null,
      2,
    ),
  );
}

async function reloadCatalog() {
  try {
    setStatus('Lade Overlay-Liste…');
    const data = await fetchOverlayCatalog();
    overlayCatalog = data.overlays || [];
    populateOverlaySelect(overlayCatalog);
    setStatus(`Overlay-Liste geladen (${overlayCatalog.length} Einträge).`, JSON.stringify(data, null, 2));
  } catch (error) {
    setStatus('Fehler beim Laden der Overlay-Liste.', String(error));
  }
}

overlaySelect.addEventListener('change', async (event) => {
  try {
    await applyOverlay(event.target.value);
  } catch (error) {
    setStatus('Fehler beim Anwenden des Overlays.', String(error));
  }
});

reloadButton.addEventListener('click', reloadCatalog);

map.on('load', async () => {
  await reloadCatalog();
});
