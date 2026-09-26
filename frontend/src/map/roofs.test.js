import { describe, expect, it } from 'vitest';
import { orientedRect, roofTriangles, roofType } from './roofs.js';

function rotated(w, h, deg, cx, cy) {
  const a = (deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]
    .map(([x, y]) => [cx + x * c - y * s, cy + x * s + y * c]);
}

describe('orientedRect', () => {
  it('recovers a rotated rectangle', () => {
    const r = orientedRect(rotated(20, 10, 30, 5, 5));
    expect(r.length).toBeCloseTo(20);
    expect(r.width).toBeCloseTo(10);
    expect(r.cx).toBeCloseTo(5);
    expect(r.cy).toBeCloseTo(5);
    expect(Math.abs(Math.sin(r.angle - Math.PI / 6))).toBeCloseTo(0);
  });
  it('long axis wins for a tall rectangle', () => {
    const r = orientedRect(rotated(6, 18, 0, 0, 0));
    expect(r.length).toBeCloseTo(18);
    expect(Math.abs(Math.cos(r.angle))).toBeCloseTo(0);
  });
});

describe('roofType', () => {
  const L = [[0, 0], [20, 0], [20, 10], [10, 10], [10, 20], [0, 20]];
  it('rectangular house -> gable', () => expect(roofType('house', rotated(12, 8, 10, 0, 0))).toBe('gable'));
  it('L-shaped house -> hip', () => expect(roofType('house', L)).toBe('hip'));
  it('apartment -> flat', () => expect(roofType('apartment', L)).toBe('flat'));
  it('other -> none', () => expect(roofType('other', L)).toBe('none'));
});

describe('roofTriangles', () => {
  const rect = { cx: 0, cy: 0, angle: 0, length: 12, width: 8 };
  it('gable has ridge height 0.45 * width and 6 triangles', () => {
    const t = roofTriangles(rect, 'gable');
    expect(t).toHaveLength(18);
    expect(Math.max(...t.map((p) => p[2]))).toBeCloseTo(3.6);
  });
  it('hip ridge is shorter than the base', () => {
    const t = roofTriangles(rect, 'hip');
    const ridge = t.filter((p) => p[2] > 0).map((p) => p[0]);
    expect(Math.max(...ridge)).toBeCloseTo(2);
  });
});
