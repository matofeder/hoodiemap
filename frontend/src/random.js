export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function seedFromCoords(lat, lon) {
  return (Math.imul(Math.round(lat * 1e5), 73856093) ^ Math.imul(Math.round(lon * 1e5), 19349663)) >>> 0;
}

export function hashPoint(x, y) {
  let h = Math.imul(Math.round(x * 10), 73856093) ^ Math.imul(Math.round(y * 10), 19349663);
  h = Math.imul(h ^ (h >>> 13), 0x5bd1e995);
  return (h ^ (h >>> 15)) >>> 0;
}
