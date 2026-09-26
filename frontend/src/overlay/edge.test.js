import { describe, expect, it } from 'vitest';
import { edgePoint, resolveOverlaps } from './edge.js';

const C = { x: 400, y: 300 };

describe('edgePoint', () => {
  it.each([
    [{ x: 0, y: -1 }, { x: 400, y: 30 }],
    [{ x: 1, y: 0 }, { x: 740, y: 300 }],
    [{ x: 0, y: 1 }, { x: 400, y: 570 }],
    [{ x: -1, y: 0 }, { x: 60, y: 300 }],
  ])('dir %o', (dir, expected) => expect(edgePoint(C, dir, 50, 20, 800, 600)).toEqual(expected));

  it('stays inside a 320 px wide widget', () => {
    const p = edgePoint({ x: 160, y: 120 }, { x: 0.8, y: -0.6 }, 60, 18, 320, 240);
    expect(p.x).toBeLessThanOrEqual(320 - 70);
    expect(p.y).toBeGreaterThanOrEqual(28);
  });
});

describe('resolveOverlaps', () => {
  it('separates two badges on the same edge', () => {
    const [a, b] = resolveOverlaps([{ x: 740, y: 300, w: 100, h: 40 }, { x: 740, y: 310, w: 100, h: 40 }], 800, 600);
    expect(Math.abs(a.y - b.y)).toBeGreaterThanOrEqual(46 - 1e-6);
    expect(a.x).toBe(740);
  });
  it('separates three stacked badges and keeps them inside', () => {
    const boxes = resolveOverlaps([0, 1, 2].map(() => ({ x: 740, y: 30, w: 100, h: 40 })), 800, 600);
    for (let i = 0; i < 3; i++) {
      expect(boxes[i].y).toBeGreaterThanOrEqual(30);
      for (let j = i + 1; j < 3; j++) expect(Math.abs(boxes[i].y - boxes[j].y)).toBeGreaterThanOrEqual(46 - 1e-6);
    }
  });
});
