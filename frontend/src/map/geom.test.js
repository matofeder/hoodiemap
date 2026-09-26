import { describe, expect, it } from 'vitest';
import { centroid, convexHull, distToPolygon, distToPolyline, pointInPolygon, polygonArea } from './geom.js';

const sq = [[0, 0], [10, 0], [10, 10], [0, 10]];

describe('geom', () => {
  it('area', () => expect(polygonArea(sq)).toBe(100));
  it('centroid', () => expect(centroid(sq)).toEqual([5, 5]));
  it('point in polygon', () => {
    expect(pointInPolygon([5, 5], sq)).toBe(true);
    expect(pointInPolygon([15, 5], sq)).toBe(false);
  });
  it('distances', () => {
    expect(distToPolyline([5, 3], [[0, 0], [10, 0]])).toBe(3);
    expect(distToPolygon([5, 5], sq)).toBe(0);
    expect(distToPolygon([13, 5], sq)).toBe(3);
  });
  it('convex hull drops inner points', () => expect(convexHull([...sq, [5, 5]])).toHaveLength(4));
});
