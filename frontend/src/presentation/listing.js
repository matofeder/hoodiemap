import { formatDistance } from '../format.js';
import { travelTime } from '../overlay/describe.js';
import { categoryInfo } from '../palette.js';

const EUR = new Intl.NumberFormat('sk-SK', { maximumFractionDigits: 0 });
const AREA = new Intl.NumberFormat('sk-SK', { maximumFractionDigits: 1 });

export function formatPrice(price, offer = 'sale') {
  if (price == null) return 'Cena na vyžiadanie';
  const amount = `${EUR.format(price)} €`;
  return offer === 'rent' ? `${amount}/mes.` : amount;
}

export function formatArea(m2) {
  return `${AREA.format(m2)} m²`;
}

export function roomsLabel(n) {
  if (n === 1) return '1 izba';
  if (n >= 2 && n <= 4) return `${n} izby`;
  return `${n} izieb`;
}

export function floorLabel(floor, total) {
  const base = floor === 0 ? 'prízemie' : floor < 0 ? `${-floor}. podzemné podlažie` : `${floor}. poschodie`;
  return total ? `${base} z ${total}` : base;
}

export const PROPERTY_TYPES = { flat: 'Byt', house: 'Rodinný dom', land: 'Pozemok', other: 'Iná nehnuteľnosť' };
export const CONDITIONS = {
  new: 'Novostavba',
  renovated: 'Po rekonštrukcii',
  partly_renovated: 'Čiastočná rekonštrukcia',
  original: 'Pôvodný stav',
  under_construction: 'Vo výstavbe',
};
export const FEATURES = {
  balcony: 'Balkón', loggia: 'Lódžia', terrace: 'Terasa', elevator: 'Výťah',
  cellar: 'Pivnica', parking: 'Parkovanie', garage: 'Garáž', garden: 'Záhrada',
};
export const ENERGY_CLASSES = ['A0', 'A1', 'A', 'B', 'C', 'D', 'E', 'F', 'G'];

// The short row under the title: what a buyer scans first.
export function keyFacts(params = {}) {
  return [
    params.rooms != null ? roomsLabel(params.rooms) : null,
    params.area_m2 != null ? formatArea(params.area_m2) : null,
    params.land_m2 != null ? `pozemok ${formatArea(params.land_m2)}` : null,
    params.floor != null ? floorLabel(params.floor, params.floors_total) : null,
    params.condition ? CONDITIONS[params.condition] : null,
  ].filter(Boolean);
}

export function paramRows(params = {}) {
  return [
    ['Typ', params.property_type && PROPERTY_TYPES[params.property_type]],
    ['Počet izieb', params.rooms != null && String(params.rooms)],
    ['Úžitková plocha', params.area_m2 != null && formatArea(params.area_m2)],
    ['Pozemok', params.land_m2 != null && formatArea(params.land_m2)],
    ['Poschodie', params.floor != null && floorLabel(params.floor, params.floors_total)],
    ['Stav', params.condition && CONDITIONS[params.condition]],
    ['Energetická trieda', params.energy_class],
    ['Rok výstavby', params.year_built != null && String(params.year_built)],
  ].filter(([, v]) => v).map(([label, value]) => ({ label, value }));
}

export function featureLabels(features = []) {
  return features.map((f) => FEATURES[f]).filter(Boolean);
}

/**
 * "Lokalita v číslach": every POI the scene found (on the map and beyond it), nearest first.
 * The scene already keeps only the nearest one per category (two for cities).
 */
export function localityRows(scene) {
  const pois = [...(scene?.near_pois ?? []), ...(scene?.far_pois ?? [])]
    .filter((p) => Number.isFinite(p.distance_m));
  return pois
    .sort((a, b) => a.distance_m - b.distance_m)
    .map((p) => {
      const { label, color } = categoryInfo(p.category);
      const name = (p.name ?? '').trim();
      const city = p.category === 'city' && name;
      return {
        category: p.category,
        color,
        label: city ? name : (p.kind ?? label),
        name: city ? 'mesto' : name && name !== label ? name : null,
        distance: formatDistance(p.distance_m),
        time: travelTime(p.distance_m).replace(/^≈ /, ''),
      };
    });
}

/** Paragraphs from a plain-text description: blank lines split, single newlines stay inside. */
export function paragraphs(text) {
  return (text ?? '').split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
}

export function formatDate(iso) {
  return new Date(iso).toLocaleDateString('sk-SK', { day: 'numeric', month: 'numeric', year: 'numeric' });
}
