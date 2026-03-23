const statusBox = document.getElementById('status-box');
const overlaySelect = document.getElementById('overlay-select');
const reloadButton = document.getElementById('reload-button');

function setStatus(message, extra) {
  statusBox.textContent = extra ? `${message}\n\n${extra}` : message;
}

const protocol = new pmtiles.Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

const DEFAULT_GLYPHS = 'https://tiles.oe5ith.at/assets/fonts/{fontstack}/{range}.pbf';
const DEFAULT_SPRITE = 'https://tiles.oe5ith.at/assets/sprites/oe5ith-markers';

const map = new maplibregl.Map({
  container: 'map',
  center: [13.8, 48.2],
  zoom: 7,
  hash: true,
  style: {
    version: 8,
    glyphs: DEFAULT_GLYPHS,
    sprite: DEFAULT_SPRITE,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '© OpenStreetMap-Mitwirkende',
        maxzoom: 19,
      },
    },
    layers: [
      {
        id: 'osm',
        type: 'raster',
        source: 'osm',
      },
    ],
  },
});

map.addControl(new maplibregl.NavigationControl(), 'top-right');

let overlayCatalog = [];
let activeOverlay = null;
let activeSources = [];
let activeLayers = [];

function removeActiveOverlay() {
  for (const layerId of activeLayers.slice().reverse()) {
    if (map.getLayer(layerId)) {
      map.removeLayer(layerId);
    }
  }
  for (const sourceId of activeSources) {
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }
  }
  activeLayers = [];
  activeSources = [];
  activeOverlay = null;
}

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
  const sourceIds = Object.keys(style.sources || {});
  const layers = [];

  for (const layer of style.layers || []) {
    if (!layer.source || !sourceIds.includes(layer.source)) {
      continue;
    }
    if (layer.type === 'background' || layer.source === 'osm') {
      continue;
    }
    layers.push(cloneStyleLayer(layer));
  }

  return { sourceIds, layers };
}

async function applyOverlay(styleFile) {
  removeActiveOverlay();

  if (!styleFile) {
    setStatus('Kein Overlay ausgewählt.');
    return;
  }

  const style = await fetchOverlayStyle(styleFile);
  const { sourceIds, layers } = normalizeOverlayLayers(style);

  for (const [sourceId, sourceDef] of Object.entries(style.sources || {})) {
    map.addSource(sourceId, sourceDef);
    activeSources.push(sourceId);
  }

  for (const layer of layers) {
    map.addLayer(layer);
    activeLayers.push(layer.id);
  }

  activeOverlay = style.metadata?.localTestServer || { styleFile };
  setStatus(
    `Overlay geladen: ${style.metadata?.folder || styleFile}`,
    JSON.stringify(
      {
        styleFile,
        sourceCount: activeSources.length,
        layerCount: activeLayers.length,
        pmtilesFile: activeOverlay.pmtilesFile || null,
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
