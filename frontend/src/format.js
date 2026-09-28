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
  if (poi.category === 'city' && name) return name;
  const useName = name && name.length <= maxLen && !LABEL_ONLY.has(poi.category);
  return useName ? name : categoryInfo(poi.category).label;
}

export function formatLoadTime(ms, cached) {
  const s = (Math.round(ms / 100) / 10).toFixed(1).replace('.', ',');
  return `Načítané za ${s} s · ${cached ? 'z cache' : 'nové dáta'}`;
}

const TIER_LABELS = { address: 'adresa', street: 'ulica', city: 'mesto' };

export function tierLabel(tier) {
  return TIER_LABELS[tier] ?? tier;
}

// Scene warnings that leave a visible hole in the map, in display order. Others (e.g. public_fallback) stay silent.
const WARNINGS = [
  ['poi_fetch_failed', 'Okolité miesta (obchody, školy, zastávky…) sa nepodarilo načítať.'],
  ['street_fetch_failed', 'Ulicu sa nepodarilo zvýrazniť.'],
];

export function warningText(warnings = []) {
  const parts = WARNINGS.filter(([code]) => warnings.includes(code)).map(([, text]) => text);
  return parts.length ? parts.join(' ') : null;
}
