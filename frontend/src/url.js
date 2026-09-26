export const DEFAULT_COORDS = { lat: 48.28646434486518, lon: 17.27221245956356 };

export function getCoordsFromURL(search) {
  const params = new URLSearchParams(search);
  const lat = parseFloat(params.get('lat'));
  const lon = parseFloat(params.get('lon'));
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lon };
}

export function isFixture(search) {
  return new URLSearchParams(search).get('fixture') === 'true';
}

const TIERS = new Set(['address', 'street', 'city']);

export function getViewFromURL(search) {
  const coords = getCoordsFromURL(search);
  if (!coords) return null;
  const p = new URLSearchParams(search);
  const tier = TIERS.has(p.get('tier')) ? p.get('tier') : 'address';
  return { ...coords, tier, name: p.get('name') || null, label: p.get('label') || null };
}

export function viewToSearch(view) {
  const p = new URLSearchParams({ lat: String(view.lat), lon: String(view.lon), tier: view.tier });
  if (view.name) p.set('name', view.name);
  if (view.label) p.set('label', view.label);
  return `?${p}`;
}

export function sceneUrl(view, fixture) {
  const p = new URLSearchParams({ lat: String(view.lat), lon: String(view.lon), tier: view.tier });
  if (view.tier === 'street' && view.name) p.set('name', view.name);
  if (fixture) p.set('fixture', 'true');
  return `/api/scene?${p}`;
}
