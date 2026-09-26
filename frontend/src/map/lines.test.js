import { describe, expect, it } from 'vitest';
import { cumulativeLengths, dashSegments, offsetLines, pointAlong, ribbonTriangles } from './lines.js';

const line = [[0, 0], [10, 0], [10, 10]];

describe('lines', () => {
  it('cumulative lengths', () => expect(cumulativeLengths(line)).toEqual([0, 10, 20]));
  it('point along second segment', () => {
    const p = pointAlong(line, cumulativeLengths(line), 15);
    expect(p).toEqual({ x: 10, y: 5, dx: 0, dy: 1 });
  });
  it('point along clamps', () => expect(pointAlong(line, cumulativeLengths(line), 99).y).toBe(10));
  it('dashes', () => {
    const d = dashSegments([[0, 0], [20, 0]], 4, 5);
    expect(d).toHaveLength(3);
    expect(d[1]).toEqual([[9, 0], [13, 0]]);
  });
  it('ribbon triangle count: 2 per segment + 12 per vertex', () =>
    expect(ribbonTriangles([[[0, 0], [10, 0]]], 2)).toHaveLength((2 + 24) * 6));
  it('offset lines run parallel on both sides', () => {
    const [a, b] = offsetLines([[0, 0], [10, 0]], 2);
    expect(a).toEqual([[0, 2], [10, 2]]);
    expect(b).toEqual([[0, -2], [10, -2]]);
  });
  it('offset lines need two points', () => expect(offsetLines([[0, 0]], 2)).toEqual([]));
});
