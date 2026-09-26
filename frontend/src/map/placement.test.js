import { describe, expect, it } from 'vitest';
import { mulberry32 } from '../random.js';
import { distToPolygon } from './geom.js';
import { carPose, planCars, seedTreePositions } from './placement.js';

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
