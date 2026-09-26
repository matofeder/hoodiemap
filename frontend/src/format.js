import { categoryInfo } from './palette.js';

export function formatDistance(meters) {
  const m = Math.round(meters / 10) * 10;
  if (m < 1000) return `${m} m`;
  const km = Math.round(m / 100) / 10;
  if (km >= 10) return `${Math.round(km)} km`;
  return `${km.toFixed(1).replace('.', ',')} km`;
}

// Stop and station names are usually just the town or square, which says less than the label.
const LABEL_ONLY = new Set(['bus_stop', 'train']);

export function poiTitle(poi, maxLen = 14) {
  const name = (poi.name ?? '').trim();
  const useName = name && name.length <= maxLen && !LABEL_ONLY.has(poi.category);
  return useName ? name : categoryInfo(poi.category).label;
}
