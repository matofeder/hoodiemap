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

  const entries = resolved.map(poi => {
    const el = _createIndicator(poi);
    container.appendChild(el);
    _positionIndicator(el, poi.bearing_deg, container);
    el.addEventListener('mouseenter', () => onHover(poi, el));
    el.addEventListener('mouseleave', () => onLeave(poi, el));
    return { el, poi };
  });

  // Reposition on resize
  const observer = new ResizeObserver(() => {
    entries.forEach(({ el, poi }) => _positionIndicator(el, poi.bearing_deg, container));
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
  for (let i = 1; i < result.length; i++) {
    for (let j = 0; j < i; j++) {
      let diff = result[i].bearing_deg - result[j].bearing_deg;
      if (diff > 180) diff -= 360;
      if (diff < -180) diff += 360;
      if (Math.abs(diff) < MIN_DIFF) {
        result[i].bearing_deg += Math.sign(diff || 1) * (MIN_DIFF - Math.abs(diff) + 2);
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
  el.innerHTML = `
    <div class="outer-poi-pill">
      <div class="outer-poi-header">
        <span class="outer-poi-dot" style="background:${color}"></span>
        <span class="outer-poi-name">${poi.name.slice(0, 22)}</span>
      </div>
      <span class="outer-poi-meta">${_formatDistance(poi.distance_m)} · ${_bearingToCardinal(poi.bearing_deg)}</span>
    </div>
  `;
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
