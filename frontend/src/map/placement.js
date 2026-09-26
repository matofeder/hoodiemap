import { PALETTE } from '../palette.js';
import { centroid, distToPolygon, distToPolyline, pointInPolygon, polygonArea } from './geom.js';
import { cumulativeLengths, pointAlong } from './lines.js';

const TREE_DENSITY_M2 = { park: 180, forest: 60 };
const MAX_SEEDED_TREES = 350;
const TREE_CLEARANCE_M = 3;
const ROAD_HALF_WIDTH = { main: 4.5, street: 3, path: 1.25, pedestrian: 5 };

export function seedTreePositions(scene, rng) {
  const out = (scene.trees ?? []).map((t) => [t.x, t.y]);
  const blocked = (p) =>
    scene.buildings.some((b) => distToPolygon(p, b.footprint) < TREE_CLEARANCE_M) ||
    scene.roads.some((r) => distToPolyline(p, r.points) < (ROAD_HALF_WIDTH[r.kind] ?? 3) + TREE_CLEARANCE_M);
  let budget = MAX_SEEDED_TREES;
  for (const layer of ['forest', 'park']) {
    for (const ring of scene.areas?.[layer] ?? []) {
      const want = Math.min(budget, Math.floor(polygonArea(ring) / TREE_DENSITY_M2[layer]));
      const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      let placed = 0;
      for (let tries = 0; placed < want && tries < want * 6; tries++) {
        const p = [x0 + rng() * (x1 - x0), y0 + rng() * (y1 - y0)];
        if (!pointInPolygon(p, ring) || blocked(p)) continue;
        out.push(p);
        placed++;
      }
      budget -= placed;
    }
  }
  return out;
}

const MAX_CARS = 6;
const METERS_PER_CAR = 60;
const MIN_ROAD_M = 20;
const LANE_OFFSET_M = 2;
const SIDEWALK_M = 0.9; // pedestrians walk just outside the carriageway
const BIKE_EDGE_M = 0.9; // cyclists ride near the right edge

// Spread movers over the longest suitable roads. lane(kind, rng) gives the sideways offset
// from the centre line (positive = right-hand side in the direction of travel).
function planMovers(roads, rng, { kinds, max, metersPer, speed: [s0, s1], lane, colors }) {
  const usable = roads
    .filter((r) => kinds.includes(r.kind))
    .map((r) => ({ pts: r.points, cum: cumulativeLengths(r.points), kind: r.kind }))
    .filter((r) => r.cum.at(-1) >= MIN_ROAD_M)
    .sort((a, b) => b.cum.at(-1) - a.cum.at(-1));
  const total = usable.reduce((sum, r) => sum + r.cum.at(-1), 0);
  const n = Math.min(max, Math.floor(total / metersPer));
  return Array.from({ length: n }, (_, i) => {
    const road = usable[i % usable.length];
    return {
      road,
      speed: s0 + rng() * (s1 - s0),
      offset: rng() * road.cum.at(-1) * 2,
      color: colors[i % colors.length],
      lane: lane(road.kind, rng),
      phase: i * 1.7,
    };
  });
}

export function planCars(roads, rng, max = MAX_CARS) {
  return planMovers(roads, rng, {
    kinds: ['main', 'street'], max, metersPer: METERS_PER_CAR, speed: [8, 14],
    lane: () => LANE_OFFSET_M, colors: PALETTE.cars,
  });
}

export function planPedestrians(roads, rng) {
  return planMovers(roads, rng, {
    kinds: ['path', 'street', 'main'], max: 16, metersPer: 35, speed: [1.3, 2.1],
    lane: (kind, r) => (kind === 'path' ? 0.5 : ROAD_HALF_WIDTH[kind] + SIDEWALK_M) * (r() < 0.5 ? -1 : 1),
    colors: PALETTE.shirts,
  });
}

export function planCyclists(roads, rng) {
  return planMovers(roads, rng, {
    kinds: ['path', 'street'], max: 5, metersPer: 110, speed: [4, 6],
    lane: (kind) => (kind === 'path' ? 0.4 : ROAD_HALF_WIDTH[kind] - BIKE_EDGE_M),
    colors: PALETTE.shirts.slice().reverse(),
  });
}

// Back and forth along the road; the lane offset stays on the right of the direction of travel.
export function carPose(car, t) {
  const L = car.road.cum.at(-1);
  const d = (car.offset + car.speed * t) % (2 * L);
  const forward = d < L;
  const p = pointAlong(car.road.pts, car.road.cum, forward ? d : 2 * L - d);
  const dx = forward ? p.dx : -p.dx, dy = forward ? p.dy : -p.dy;
  const lane = car.lane ?? LANE_OFFSET_M;
  return { x: p.x + dy * lane, y: p.y - dx * lane, heading: Math.atan2(dy, dx) };
}

// Extra strollers inside pedestrian zones: slower, spread across the whole width.
export function planZoneWalkers(roads, rng) {
  return planMovers(roads, rng, {
    kinds: ['pedestrian'], max: 10, metersPer: 12, speed: [0.9, 1.6],
    lane: (kind, r) => (r() * 2 - 1) * (ROAD_HALF_WIDTH.pedestrian - 1),
    colors: PALETTE.shirts.slice(2).concat(PALETTE.shirts.slice(0, 2)),
  });
}

const DECOR_SPACING_M = 11;
const DECOR_KINDS = ['bench', 'lamp', 'planter'];
const DECOR_CLEARANCE_M = 1.5;

// Benches, lamps and planters along both edges of pedestrian zones, cycling through the kinds.
// angle: rotation (radians, CCW from +x) that makes a bench face the zone's centre line.
export function planStreetDecor(scene) {
  const r = scene.radius_m, out = [];
  const lines = scene.roads.filter((rd) => rd.kind === 'pedestrian').map((rd) => rd.points);
  const edge = ROAD_HALF_WIDTH.pedestrian - 0.8;
  let k = 0;
  for (const pts of lines) {
    const cum = cumulativeLengths(pts), L = cum.at(-1);
    for (let s = DECOR_SPACING_M / 2; s < L; s += DECOR_SPACING_M) {
      const p = pointAlong(pts, cum, s);
      for (const side of [1, -1]) {
        const x = p.x + p.dy * edge * side, y = p.y - p.dx * edge * side;
        if (Math.abs(x) > r - 2 || Math.abs(y) > r - 2) continue;
        if (scene.buildings.some((b) => distToPolygon([x, y], b.footprint) < DECOR_CLEARANCE_M)) continue;
        out.push({ kind: DECOR_KINDS[k++ % DECOR_KINDS.length], x, y, angle: Math.atan2(p.dx * side, -p.dy * side) });
      }
    }
  }
  for (const ring of scene.areas?.plaza ?? []) {
    const ring2 = ring.length > 2 ? ring : null;
    if (!ring2) continue;
    const [cx, cy] = centroid(ring2);
    for (let i = 0; i < ring2.length; i++) {
      const [x0, y0] = ring2[i], [x1, y1] = ring2[(i + 1) % ring2.length];
      const x = x0 + (x1 - x0) / 2 + (cx - x0 - (x1 - x0) / 2) * 0.2;
      const y = y0 + (y1 - y0) / 2 + (cy - y0 - (y1 - y0) / 2) * 0.2;
      if (!pointInPolygon([x, y], ring2)) continue;
      out.push({ kind: DECOR_KINDS[k++ % DECOR_KINDS.length], x, y, angle: Math.atan2(cy - y, cx - x) });
    }
  }
  return out;
}

const TERRACE_GAP_M = 2.4;
const TABLE_SPACING_M = 3;
const TERRACE_MIN_EDGE_M = 5;
const TABLE_CLEARANCE_M = 1.2;
// Horizontal direction towards the iso camera in backend x/y (camera sits south-east).
const CAMERA_XY = [0.6, -0.8];

// Café tables in front of the café's building: on a wall long enough, with free space (no other
// building, no carriageway), preferring the side the camera sees.
export function planTerraces(scene) {
  const out = [], r = scene.radius_m;
  const carriageways = scene.roads.filter((rd) => rd.kind === 'main' || rd.kind === 'street');
  const free = ([x, y]) =>
    Math.abs(x) < r - 2 && Math.abs(y) < r - 2 &&
    !scene.buildings.some((b) => distToPolygon([x, y], b.footprint) < TABLE_CLEARANCE_M) &&
    !carriageways.some((rd) => distToPolyline([x, y], rd.points) < ROAD_HALF_WIDTH[rd.kind] + 0.8);
  for (const poi of scene.near_pois) {
    if (poi.category !== 'food' || poi.building_index == null) continue;
    const fp = scene.buildings[poi.building_index]?.footprint;
    if (!fp) continue;
    let best = null, bestScore = -0.3;
    for (let i = 0; i < fp.length; i++) {
      const [ax, ay] = fp[i], [bx, by] = fp[(i + 1) % fp.length];
      const len = Math.hypot(bx - ax, by - ay);
      if (len < TERRACE_MIN_EDGE_M) continue;
      const tx = (bx - ax) / len, ty = (by - ay) / len, mx = (ax + bx) / 2, my = (ay + by) / 2;
      let nx = ty, ny = -tx;
      if (pointInPolygon([mx + nx, my + ny], fp)) { nx = -nx; ny = -ny; }
      const score = nx * CAMERA_XY[0] + ny * CAMERA_XY[1];
      if (score <= bestScore) continue;
      const ks = len >= 8 ? [-1, 0, 1] : [-0.5, 0.5];
      const tables = ks.map((k) => ({
        x: mx + nx * TERRACE_GAP_M + tx * k * TABLE_SPACING_M,
        y: my + ny * TERRACE_GAP_M + ty * k * TABLE_SPACING_M,
        angle: Math.atan2(ty, tx),
      }));
      if (!tables.every((t) => free([t.x, t.y]))) continue;
      best = tables;
      bestScore = score;
    }
    if (best) out.push(...best);
  }
  return out;
}

// Where pigeons and chatting groups gather: pedestrian zone, else plaza, else the biggest park.
export function gatheringSpots(scene) {
  const peds = scene.roads.filter((rd) => rd.kind === 'pedestrian')
    .map((rd) => ({ pts: rd.points, cum: cumulativeLengths(rd.points) }))
    .sort((a, b) => b.cum.at(-1) - a.cum.at(-1));
  const spots = [];
  for (const { pts, cum } of peds.slice(0, 2)) {
    for (const f of [0.3, 0.7]) {
      const p = pointAlong(pts, cum, cum.at(-1) * f);
      spots.push([p.x, p.y]);
    }
  }
  for (const ring of scene.areas?.plaza ?? []) spots.push(centroid(ring));
  if (!spots.length) {
    const parks = [...(scene.areas?.park ?? [])].sort((a, b) => polygonArea(b) - polygonArea(a));
    if (parks[0] && polygonArea(parks[0]) > 150) spots.push(centroid(parks[0]));
  }
  const r = scene.radius_m;
  return spots.filter(([x, y]) => Math.abs(x) < r - 8 && Math.abs(y) < r - 8);
}
