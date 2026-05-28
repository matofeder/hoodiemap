import { POI_COLORS } from './colors.js';
import { initFrame } from './frame.js';

const CATEGORY_EMOJI = {
  hospital:      '🏥',
  grocery:       '🛒',
  school:        '🏫',
  pharmacy:      '💊',
  pub:           '🍺',
  bar:           '🍸',
  restaurant:    '🍽',
  public_office: '🏛',
  bus_stop:      '🚌',
  bike_parking:  '🚲',
  parking:       '🅿',
  train:         '🚉',
};

/**
 * Builds the full infographic DOM inside `rootEl`.
 * Returns { canvasSlot } — the div where Three.js should mount.
 */
export function initInfographic(rootEl, sceneData) {
  rootEl.innerHTML = '';
  rootEl.className = 'infographic-root';

  const header = _buildHeader(sceneData.address || '');
  const body = document.createElement('div');
  body.className = 'infographic-body';

  const leftPanel = _buildPoiPanel(sceneData.pois.slice(0, 3), sceneData.bbox_m || 600);
  leftPanel.classList.add('infographic-panel-left');

  const canvasSlot = document.createElement('div');
  canvasSlot.className = 'infographic-canvas-slot';

  const rightPanel = _buildPoiPanel(sceneData.pois.slice(3, 6), sceneData.bbox_m || 600);
  rightPanel.classList.add('infographic-panel-right');

  body.append(leftPanel, canvasSlot, rightPanel);

  const strip = _buildTransportStrip(sceneData.transport || []);

  rootEl.append(header, body, strip);

  if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
    initFrame(
      canvasSlot,
      sceneData.outer_pois,
      sceneData.center.lat,
      sceneData.center.lon,
      () => {},
      () => {},
    );
  }

  return { canvasSlot };
}

function _buildHeader(address) {
  const el = document.createElement('div');
  el.className = 'infographic-header';

  const title = document.createElement('span');
  title.className = 'infographic-title';
  title.textContent = '◈ NEIGHBOURHOOD MAP';

  const addr = document.createElement('span');
  addr.className = 'infographic-address';
  addr.textContent = address;

  el.append(title, addr);
  return el;
}

function _buildPoiPanel(pois, displayRadiusM) {
  const el = document.createElement('div');
  el.className = 'infographic-panel';

  pois.forEach(poi => {
    const color = POI_COLORS[poi.category] || '#888888';
    const emoji = CATEGORY_EMOJI[poi.category] || '📍';
    const fill = Math.min(100, Math.round((poi.distance_m / displayRadiusM) * 100));
    const cardinal = _bearingToCardinal(poi.bearing_deg ?? 0);
    const distLabel = poi.distance_m >= 1000
      ? `${(poi.distance_m / 1000).toFixed(1)} km`
      : `${poi.distance_m} m`;

    const card = document.createElement('div');
    card.className = 'poi-card';
    card.style.setProperty('--cat-color', color);

    card.innerHTML = `
      <div class="poi-card-emoji-name">${emoji} ${_escapeHtml(poi.name)}</div>
      <div class="poi-card-meta">${distLabel} · ${cardinal}</div>
      <div class="poi-card-bar-track">
        <div class="poi-card-bar-fill" style="width:${fill}%"></div>
      </div>
    `;
    el.appendChild(card);
  });

  return el;
}

function _buildTransportStrip(transport) {
  const el = document.createElement('div');
  el.className = 'infographic-strip';

  if (transport.length === 0) return el;

  transport.slice(0, 5).forEach(t => {
    const emoji = CATEGORY_EMOJI[t.category] || '🚏';
    const distLabel = t.distance_m >= 1000
      ? `${(t.distance_m / 1000).toFixed(1)} km`
      : `${t.distance_m} m`;
    const cardinal = _bearingToCardinal(t.bearing_deg ?? 0);

    const pill = document.createElement('span');
    pill.className = 'transport-pill';
    pill.textContent = `${emoji} ${_escapeHtml(t.name)} · ${distLabel} ${cardinal}`;
    el.appendChild(pill);
  });

  return el;
}

function _bearingToCardinal(deg) {
  if (deg == null) return '';
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(((deg % 360) + 360) % 360 / 45) % 8];
}

function _escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
