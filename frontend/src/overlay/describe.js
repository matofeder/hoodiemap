import { formatDistance } from '../format.js';
import { categoryInfo } from '../palette.js';

// Rough door-to-door estimates from straight-line distance.
const WALK_M_PER_MIN = 80;
const WALK_DETOUR = 1.3;
const WALK_MAX_M = 2500;
const DRIVE_M_PER_MIN = 50_000 / 60;
const DRIVE_DETOUR = 1.25;

export function travelTime(meters) {
  if (meters <= WALK_MAX_M) return `≈ ${Math.max(1, Math.ceil((meters * WALK_DETOUR) / WALK_M_PER_MIN))} min pešo`;
  return `≈ ${Math.max(1, Math.round((meters * DRIVE_DETOUR) / DRIVE_M_PER_MIN))} min autom`;
}

const DAYS = { Mo: 'Po', Tu: 'Ut', We: 'St', Th: 'Št', Fr: 'Pi', Sa: 'So', Su: 'Ne' };

// OSM opening_hours in Slovak; the syntax is rich, so only the common tokens are translated.
export function openingHours(raw) {
  if (!raw) return null;
  if (raw.trim() === '24/7') return 'nonstop';
  return raw
    .replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su)\b/g, (d) => DAYS[d])
    .replace(/\bPH\b/g, 'sviatky')
    .replace(/\boff\b/g, 'zatvorené');
}

export function floorsLabel(height) {
  const n = Math.max(1, Math.round(height / 3));
  const word = n === 1 ? 'podlažie' : n <= 4 ? 'podlažia' : 'podlaží';
  return `${n} ${word}`;
}

const KIND_LABEL = {
  house: 'Rodinný dom',
  apartment: 'Bytový dom',
  commercial: 'Obchod a služby',
  civic: 'Verejná budova',
  other: 'Garáž / prístavba',
};

export function poiInfo(poi) {
  const { label: categoryLabel, color } = categoryInfo(poi.category);
  const label = poi.kind ?? categoryLabel;
  const where = `${formatDistance(poi.distance_m)} · ${travelTime(poi.distance_m)}`;
  const lines = [poi.category === 'city' ? where : `${label} · ${where}`];
  const hours = openingHours(poi.opening_hours);
  if (hours) {
    const [first, ...rest] = hours.split(/;\s*/);
    lines.push(`Otvorené: ${first}`, ...rest);
  }
  return { title: poi.name || label, color, lines };
}

export function buildingInfo(building, { isProperty = false, poi = null } = {}) {
  if (poi) return poiInfo(poi);
  const kind = KIND_LABEL[building.kind] ?? 'Budova';
  return {
    title: isProperty ? `Na predaj · ${kind}` : kind,
    lines: [`≈ ${floorsLabel(building.height)}`],
  };
}
