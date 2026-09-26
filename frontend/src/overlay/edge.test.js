import { describe, expect, it } from 'vitest';
import { boxHitsPoly, edgePoint, placeOutside, rayExit, resolveOverlaps, separateLabels, spreadAround } from './edge.js';

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

describe('badges around the map diamond', () => {
  // Iso diamond ~ what the slab projects to: centre (400, 300), 600 x 300.
  const diamond = [{ x: 100, y: 300 }, { x: 400, y: 150 }, { x: 700, y: 300 }, { x: 400, y: 450 }];
  const C = { x: 400, y: 300 };
  const box = (p, w = 90, h = 34) => ({ x: p.x, y: p.y, w, h });

  it('rayExit finds where a ray from the centre leaves the polygon', () => {
    expect(rayExit(C, { x: 1, y: 0 }, diamond)).toBeCloseTo(300);
    expect(rayExit(C, { x: 0, y: -1 }, diamond)).toBeCloseTo(150);
  });

  it('boxHitsPoly detects overlap and clearance', () => {
    expect(boxHitsPoly(box({ x: 700, y: 300 }), diamond)).toBe(true);
    expect(boxHitsPoly(box({ x: 800, y: 300 }), diamond)).toBe(false);
    expect(boxHitsPoly({ x: 400, y: 300, w: 2000, h: 2000 }, diamond)).toBe(true); // box swallows the polygon
  });

  it('placeOutside puts the badge just outside the diamond, in its direction', () => {
    for (const d of [{ x: 1, y: 0 }, { x: 0, y: -1 }, { x: Math.SQRT1_2, y: Math.SQRT1_2 }, { x: -0.8, y: 0.6 }]) {
      const p = placeOutside(C, d, 45, 17, diamond, 12);
      expect(boxHitsPoly(box(p), diamond)).toBe(false);
      // close to the edge: nudging it 20 px back towards the centre would hit the map
      expect(boxHitsPoly(box({ x: p.x - d.x * 20, y: p.y - d.y * 20 }), diamond)).toBe(true);
    }
  });

  it('spreadAround separates colliding badges, keeps them off the map and inside the bounds', () => {
    const d = { x: 1, y: 0 };
    const boxes = [0, 1, 2].map(() => ({ ...box(placeOutside(C, d, 45, 17, diamond, 12)), dir: d }));
    const address = { x: 80, y: 580, w: 150, h: 30 };
    spreadAround(boxes, diamond, 800, 600, [address]);
    const overlaps = (a, b) => Math.abs(a.x - b.x) < (a.w + b.w) / 2 && Math.abs(a.y - b.y) < (a.h + b.h) / 2;
    for (let i = 0; i < boxes.length; i++) {
      expect(boxHitsPoly(boxes[i], diamond)).toBe(false);
      expect(overlaps(boxes[i], address)).toBe(false);
      expect(boxes[i].x + boxes[i].w / 2).toBeLessThanOrEqual(800);
      for (let j = i + 1; j < boxes.length; j++) expect(overlaps(boxes[i], boxes[j])).toBe(false);
    }
  });
});
