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

export function floorsLabel(n) {
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

// OSM building / amenity / shop / tourism values (from the backend's `type`) in Slovak.
const TYPE_LABEL = {
  apartments: 'Bytový dom', house: 'Rodinný dom', detached: 'Rodinný dom', semidetached_house: 'Dvojdom',
  terrace: 'Radový dom', bungalow: 'Bungalov', garage: 'Garáž', garages: 'Garáže', shed: 'Kôlňa', barn: 'Stodola',
  retail: 'Obchod a služby', commercial: 'Obchod a služby', office: 'Kancelárie', industrial: 'Priemyselná budova',
  warehouse: 'Sklad', school: 'Škola', kindergarten: 'Materská škola', university: 'Univerzita', college: 'Vysoká škola',
  hospital: 'Nemocnica', clinic: 'Poliklinika', doctors: 'Ambulancia', dentist: 'Zubná ambulancia',
  church: 'Kostol', cathedral: 'Katedrála', chapel: 'Kaplnka', place_of_worship: 'Kostol',
  hotel: 'Hotel', hostel: 'Hostel', guest_house: 'Penzión', civic: 'Verejná budova', public: 'Verejná budova',
  government: 'Úrad', townhall: 'Radnica', train_station: 'Železničná stanica', supermarket: 'Supermarket',
  mall: 'Nákupné centrum', sports_hall: 'Športová hala', restaurant: 'Reštaurácia', cafe: 'Kaviareň',
  pharmacy: 'Lekáreň', bank: 'Banka', post_office: 'Pošta', police: 'Polícia', fire_station: 'Hasičská stanica',
  theatre: 'Divadlo', cinema: 'Kino', library: 'Knižnica', museum: 'Múzeum', gallery: 'Galéria',
  marketplace: 'Tržnica', parking: 'Parkovací dom', monastery: 'Kláštor', tower: 'Veža', castle: 'Kaštieľ',
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

// Only what OSM states: name, type, address, floors, year, heritage — and how far it is from the
// property. The old "≈ N podlaží" guessed from the rendered height is gone (often wildly off).
export function buildingInfo(building, { isProperty = false, poi = null, distanceM = null } = {}) {
  if (poi) return poiInfo(poi);
  const typeLabel = TYPE_LABEL[building.type];
  const label = typeLabel ?? KIND_LABEL[building.kind] ?? 'Budova';
  const title = isProperty ? `Na predaj · ${label}` : building.name || label;
  const lines = [];
  // Under a name, only a stated type is worth a mention; the kind is a guess from size and shape.
  const kindAndAddress = [!isProperty && building.name ? typeLabel : null, building.address].filter(Boolean);
  if (kindAndAddress.length) lines.push(kindAndAddress.join(' · '));
  const facts = [
    building.levels ? floorsLabel(building.levels) : null,
    building.year ? `postavené ${building.year}` : null,
    building.heritage ? 'pamiatka' : null,
  ].filter(Boolean);
  if (facts.length) lines.push(facts.join(' · '));
  if (!isProperty && distanceM != null) lines.push(`${formatDistance(distanceM)} od nehnuteľnosti · ${travelTime(distanceM)}`);
  return { title, lines };
}
