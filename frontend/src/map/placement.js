import { PALETTE } from '../palette.js';
import { distToPolygon, distToPolyline, pointInPolygon, polygonArea } from './geom.js';
import { cumulativeLengths, pointAlong } from './lines.js';

const TREE_DENSITY_M2 = { park: 180, forest: 60 };
const MAX_SEEDED_TREES = 350;
const TREE_CLEARANCE_M = 3;
const ROAD_HALF_WIDTH = { main: 4.5, street: 3, path: 1.25 };

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

export function planCars(roads, rng) {
  const drivable = roads
    .filter((r) => r.kind === 'main' || r.kind === 'street')
    .map((r) => ({ pts: r.points, cum: cumulativeLengths(r.points) }))
    .filter((r) => r.cum.at(-1) >= MIN_ROAD_M)
    .sort((a, b) => b.cum.at(-1) - a.cum.at(-1));
  const total = drivable.reduce((sum, r) => sum + r.cum.at(-1), 0);
  const n = Math.min(MAX_CARS, Math.floor(total / METERS_PER_CAR));
  return Array.from({ length: n }, (_, i) => {
    const road = drivable[i % drivable.length];
    return {
      road,
      speed: 8 + rng() * 6,
      offset: rng() * road.cum.at(-1) * 2,
      color: PALETTE.cars[i % PALETTE.cars.length],
    };
  });
}

export function carPose(car, t) {
  const L = car.road.cum.at(-1);
  const d = (car.offset + car.speed * t) % (2 * L);
  const forward = d < L;
  const p = pointAlong(car.road.pts, car.road.cum, forward ? d : 2 * L - d);
  const dx = forward ? p.dx : -p.dx, dy = forward ? p.dy : -p.dy;
  return { x: p.x + dy * LANE_OFFSET_M, y: p.y - dx * LANE_OFFSET_M, heading: Math.atan2(dy, dx) };
}
