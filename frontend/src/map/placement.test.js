import { describe, expect, it } from 'vitest';
import { mulberry32 } from '../random.js';
import { distToPolygon } from './geom.js';
import {
  carPose, gatheringSpots, planCars, planCyclists, planPedestrians, planStreetDecor, planTerraces, planZoneWalkers,
  seedTreePositions,
} from './placement.js';

const park = [[0, 0], [60, 0], [60, 60], [0, 60]];
const house = [[20, 20], [40, 20], [40, 40], [20, 40]];
const base = { buildings: [{ footprint: house }], roads: [], areas: { park: [park], forest: [], water: [] }, trees: [{ x: -50, y: -50 }] };

describe('seedTreePositions', () => {
  it('keeps OSM trees and seeds parks away from buildings', () => {
    const pts = seedTreePositions(base, mulberry32(1));
    expect(pts[0]).toEqual([-50, -50]);
    expect(pts.length).toBeGreaterThan(5);
    for (const p of pts.slice(1)) expect(distToPolygon(p, house)).toBeGreaterThanOrEqual(3);
  });
  it('is deterministic', () =>
    expect(seedTreePositions(base, mulberry32(7))).toEqual(seedTreePositions(base, mulberry32(7))));
  it('handles an empty scene', () =>
    expect(seedTreePositions({ buildings: [], roads: [], areas: {}, trees: [] }, mulberry32(1))).toEqual([]));
});

describe('cars', () => {
  const roads = [{ kind: 'main', points: [[-140, 0], [140, 0]] }, { kind: 'path', points: [[0, -140], [0, 140]] }];
  it('one car per 60 m of drivable road, max 6', () => {
    expect(planCars(roads, mulberry32(1))).toHaveLength(4);
    expect(planCars([], mulberry32(1))).toEqual([]);
  });
  it('drives on the right lane and turns around at the end', () => {
    const car = { ...planCars(roads, mulberry32(1))[0], offset: 0, speed: 10 };
    const a = carPose(car, 1);
    expect(a.x).toBeCloseTo(-130);
    expect(a.y).toBeCloseTo(-2);
    expect(a.heading).toBeCloseTo(0);
    const b = carPose(car, 29);
    expect(b.x).toBeCloseTo(130);
    expect(b.y).toBeCloseTo(2);
    expect(Math.abs(b.heading)).toBeCloseTo(Math.PI);
  });
});

describe('pedestrians and cyclists', () => {
  const roads = [{ kind: 'street', points: [[-140, 0], [140, 0]] }, { kind: 'path', points: [[0, -140], [0, 140]] }];
  it('pedestrians walk on sidewalks or paths, cyclists near the right edge', () => {
    const people = planPedestrians(roads, mulberry32(3));
    expect(people.length).toBe(16);
    for (const p of people) {
      expect(Math.abs(p.lane)).toBeCloseTo(p.road.kind === 'path' ? 0.5 : 3.9);
      expect(p.speed).toBeLessThan(2.2);
    }
    const bikes = planCyclists(roads, mulberry32(3));
    expect(bikes.length).toBe(5);
    for (const b of bikes) expect(b.lane).toBeCloseTo(b.road.kind === 'path' ? 0.4 : 2.1);
  });
  it('none without roads', () => {
    expect(planPedestrians([], mulberry32(1))).toEqual([]);
    expect(planCyclists([], mulberry32(1))).toEqual([]);
  });
});

describe('pedestrian zone', () => {
  const zone = {
    radius_m: 140,
    buildings: [{ footprint: [[-10, 20], [10, 20], [10, 40], [-10, 40]] }],
    roads: [{ kind: 'pedestrian', points: [[-60, 0], [60, 0]] }, { kind: 'street', points: [[-60, 60], [60, 60]] }],
    areas: { park: [], plaza: [] },
    near_pois: [{ category: 'food', x: 0, y: 28, building_index: 0 }],
  };

  it('puts decor on both edges, cycling bench / lamp / planter', () => {
    const d = planStreetDecor(zone);
    expect(d.length).toBeGreaterThan(15);
    expect(d.slice(0, 3).map((x) => x.kind)).toEqual(['bench', 'lamp', 'planter']);
    for (const x of d) expect(Math.abs(Math.abs(x.y) - 4.2)).toBeLessThan(1e-6);
  });

  it('extra walkers stay inside the zone width', () => {
    const w = planZoneWalkers(zone.roads, mulberry32(2));
    expect(w.length).toBe(10);
    for (const x of w) expect(Math.abs(x.lane)).toBeLessThanOrEqual(4);
  });

  it('café tables go in front of the camera-facing wall, off the carriageway', () => {
    const t = planTerraces(zone);
    expect(t).toHaveLength(3);
    for (const x of t) expect(x.y).toBeCloseTo(17.6);
    const blocked = { ...zone, roads: [{ kind: 'main', points: [[-60, 17], [60, 17]] }] };
    for (const x of planTerraces(blocked)) expect(x.x).toBeCloseTo(12.4); // falls back to the east wall
  });

  it('gathering spots come from the pedestrian zone, else the biggest park', () => {
    expect(gatheringSpots(zone)).toEqual([[-24, 0], [24, 0]]);
    const parkOnly = { ...zone, roads: [], areas: { park: [[[0, 0], [20, 0], [20, 20], [0, 20]]] } };
    expect(gatheringSpots(parkOnly)).toEqual([[10, 10]]);
    expect(gatheringSpots({ ...zone, roads: [], areas: {} })).toEqual([]);
  });
});
