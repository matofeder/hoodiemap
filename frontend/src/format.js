import { categoryInfo } from './palette.js';

export function formatDistance(meters) {
  const m = Math.round(meters / 10) * 10;
  if (m < 1000) return `${m} m`;
  const km = Math.round(m / 100) / 10;
  if (km >= 10) return `${Math.round(km)} km`;
  return `${km.toFixed(1).replace('.', ',')} km`;
}

export function poiTitle(poi, maxLen = 14) {
  const name = (poi.name ?? '').trim();
  return name && name.length <= maxLen ? name : categoryInfo(poi.category).label;
}
