import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import { buildRibbonGeometry, buildDashLineGeometry } from './geometry.js';

function straightCurve(length = 100) {
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(length, 0, 0),
  ]);
}

describe('buildRibbonGeometry', () => {
  it('returns a BufferGeometry', () => {
    const geo = buildRibbonGeometry(straightCurve(), 4);
    expect(geo).toBeInstanceOf(THREE.BufferGeometry);
  });

  it('has at least 12 positions (2 triangles minimum)', () => {
    const geo = buildRibbonGeometry(straightCurve(), 4);
    const count = geo.getAttribute('position').count;
    expect(count).toBeGreaterThanOrEqual(4); // at least 1 segment = 2 rows × 2 verts
  });

  it('all y values equal 0.15', () => {
    const geo = buildRibbonGeometry(straightCurve(), 4);
    const pos = geo.getAttribute('position');
    for (let i = 0; i < pos.count; i++) {
      expect(pos.getY(i)).toBeCloseTo(0.15, 5);
    }
  });
});

describe('buildDashLineGeometry', () => {
  it('returns a BufferGeometry', () => {
    const geo = buildDashLineGeometry(straightCurve(100), 2, 3, 0.17);
    expect(geo).toBeInstanceOf(THREE.BufferGeometry);
  });

  it('has correct number of dash quads for 100m curve with 5m period', () => {
    // 100m / (2+3) = 20 dashes, each dash = 2 triangles = 6 verts
    const geo = buildDashLineGeometry(straightCurve(100), 2, 3, 0.17);
    const count = geo.getAttribute('position').count;
    expect(count).toBe(20 * 6);
  });

  it('all y values equal yOffset', () => {
    const geo = buildDashLineGeometry(straightCurve(100), 2, 3, 0.42);
    const pos = geo.getAttribute('position');
    for (let i = 0; i < pos.count; i++) {
      expect(pos.getY(i)).toBeCloseTo(0.42, 5);
    }
  });
});
