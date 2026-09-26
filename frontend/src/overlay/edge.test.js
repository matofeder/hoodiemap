import { describe, expect, it } from 'vitest';
import { edgePoint, resolveOverlaps, separateLabels } from './edge.js';

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

describe('resolveOverlaps in a crowded narrow widget', () => {
  const overlap = (a, b) => Math.abs(a.x - b.x) < (a.w + b.w) / 2 && Math.abs(a.y - b.y) < (a.h + b.h) / 2;
  it.each([[[40, 42, 44, 46, 48, 50]], [[350, 355, 0, 5, 10]]])('bearings %j leave no overlapping pair', (bearings) => {
    const W = 320, H = 240, c = { x: 160, y: 120 };
    const boxes = bearings.map((deg) => {
      const b = (deg * Math.PI) / 180;
      const p = edgePoint(c, { x: Math.sin(b), y: -Math.cos(b) }, 50, 13, W, H);
      return { ...p, w: 100, h: 26 };
    });
    resolveOverlaps(boxes, W, H);
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) expect(overlap(boxes[i], boxes[j])).toBe(false);
      expect(boxes[i].x - 50).toBeGreaterThanOrEqual(10 - 1e-6);
      expect(boxes[i].x + 50).toBeLessThanOrEqual(310 + 1e-6);
    }
  });
});

describe('separateLabels', () => {
  const overlaps = (a, b) => Math.abs(a.x - b.x) < (a.w + b.w) / 2 && Math.abs(a.y - b.y) < (a.h + b.h) / 2;

  it('pushes overlapping labels apart vertically', () => {
    const boxes = [{ x: 100, y: 100, w: 80, h: 20 }, { x: 110, y: 105, w: 80, h: 20 }];
    separateLabels(boxes, [], 600);
    expect(overlaps(boxes[0], boxes[1])).toBe(false);
    expect(boxes.map((b) => b.x)).toEqual([100, 110]);
  });

  it('moves a label off a fixed box without moving the fixed box', () => {
    const tag = { x: 200, y: 200, w: 60, h: 40 };
    const boxes = [{ x: 200, y: 210, w: 80, h: 20 }];
    separateLabels(boxes, [tag], 600);
    expect(tag.y).toBe(200);
    expect(overlaps(tag, boxes[0])).toBe(false);
  });

  it('leaves separate labels alone', () => {
    const boxes = [{ x: 100, y: 100, w: 50, h: 20 }, { x: 300, y: 100, w: 50, h: 20 }];
    separateLabels(boxes, [], 600);
    expect(boxes.map((b) => b.y)).toEqual([100, 100]);
  });
});
