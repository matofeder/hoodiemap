import { POI_COLORS } from './colors.js';

const PRIORITY = ['hospital', 'school', 'pharmacy', 'grocery', 'public_office', 'restaurant', 'pub', 'bar'];
const MAX_OUTER = 8;

/**
 * Renders outer POI indicators around the infographic frame.
 * Returns { highlight(poi), clear() }.
 */
export function initFrame(container, outerPois, centerLat, centerLon, onHover, onLeave) {
  const sorted = [...outerPois]
    .sort((a, b) => {
      const pa = PRIORITY.indexOf(a.category);
      const pb = PRIORITY.indexOf(b.category);
      return (pa === -1 ? 99 : pa) - (pb === -1 ? 99 : pb);
    })
    .slice(0, MAX_OUTER);

  const resolved = _resolveCollisions(sorted);

  const entries = resolved.map((resolvedPoi, idx) => {
    const originalPoi = sorted[idx];
    const el = _createIndicator({ ...originalPoi, display_bearing: originalPoi.bearing_deg });
    container.appendChild(el);
    _positionIndicator(el, resolvedPoi.bearing_deg, container);
    el.addEventListener('mouseenter', () => onHover(originalPoi, el));
    el.addEventListener('mouseleave', () => onLeave(originalPoi, el));
    return { el, poi: originalPoi, resolvedBearing: resolvedPoi.bearing_deg };
  });

  // Reposition on resize
  const observer = new ResizeObserver(() => {
    entries.forEach(({ el, resolvedBearing }) => _positionIndicator(el, resolvedBearing, container));
  });
  observer.observe(container);

  return {
    highlight(activePoi) {
      entries.forEach(({ el, poi }) => el.classList.toggle('active', poi === activePoi));
    },
    clear() {
      observer.disconnect();
      entries.forEach(({ el }) => el.remove());
    },
  };
}

export function _resolveCollisions(pois) {
  const result = pois.map(p => ({ ...p }));
  const MIN_DIFF = 15;
  let changed = true;
  let iterations = 0;
  while (changed && iterations < 10) {
    changed = false;
    iterations++;
    for (let i = 1; i < result.length; i++) {
      for (let j = 0; j < i; j++) {
        let diff = result[i].bearing_deg - result[j].bearing_deg;
        if (diff > 180) diff -= 360;
        if (diff < -180) diff += 360;
        if (Math.abs(diff) < MIN_DIFF) {
          result[i].bearing_deg += Math.sign(diff || 1) * (MIN_DIFF - Math.abs(diff) + 2);
          changed = true;
        }
      }
    }
  }
  return result;
}

export function _formatDistance(meters) {
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

export function _bearingToCardinal(deg) {
  const dirs = ['S', 'SV', 'V', 'JV', 'J', 'JZ', 'Z', 'SZ'];
  return dirs[Math.round(((deg % 360) + 360) % 360 / 45) % 8];
}

function _createIndicator(poi) {
  const color = POI_COLORS[poi.category] || '#888888';
  const el = document.createElement('div');
  el.className = 'outer-poi-indicator';
  el.dataset.category = poi.category;

  const pill = document.createElement('div');
  pill.className = 'outer-poi-pill';

  const header = document.createElement('div');
  header.className = 'outer-poi-header';

  const dot = document.createElement('span');
  dot.className = 'outer-poi-dot';
  dot.style.background = color;

  const name = document.createElement('span');
  name.className = 'outer-poi-name';
  name.textContent = poi.name.slice(0, 22);

  header.append(dot, name);

  const meta = document.createElement('span');
  meta.className = 'outer-poi-meta';
  meta.textContent = `${_formatDistance(poi.distance_m)} · ${_bearingToCardinal(poi.display_bearing ?? poi.bearing_deg)}`;

  pill.append(header, meta);
  el.appendChild(pill);
  return el;
}

function _positionIndicator(el, bearingDeg, container) {
  const W = container.clientWidth;
  const H = container.clientHeight;
  if (!W || !H) return;
  const rad = (bearingDeg * Math.PI) / 180;
  const rx = W / 2 * 0.90;
  const ry = H / 2 * 0.90;
  const x = W / 2 + rx * Math.sin(rad);
  const y = H / 2 - ry * Math.cos(rad);
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  el.style.transform = 'translate(-50%, -50%)';
}
