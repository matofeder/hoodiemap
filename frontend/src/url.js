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
