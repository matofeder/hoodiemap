import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { addBuildings, buildingIndexAt, glowGeometry } from './buildings.js';

const mat = (() => {
  const cache = new Map();
  return (color, opts = {}) => {
    const key = `${color}|${opts.flatShading ? 1 : 0}`;
    if (!cache.has(key)) cache.set(key, new THREE.MeshLambertMaterial({ color, ...opts }));
    return cache.get(key);
  };
})();

const square = (x, y, s) => [[x, y], [x + s, y], [x + s, y + s], [x, y + s]];
const buildings = [
  { footprint: square(0, 0, 10), kind: 'apartment', height: 12 },
  { footprint: square(30, 0, 10), kind: 'apartment', height: 9 },
  { footprint: square(60, 0, 8), kind: 'house', height: 6 },
];

describe('addBuildings (merged)', () => {
  it('merges into one mesh per material and tags every vertex with its building', () => {
    const added = [];
    const meshes = addBuildings({ add: (m) => added.push(m) }, buildings, null, mat, new Map());
    expect(meshes.length).toBe(added.length);
    expect(meshes.length).toBeLessThan(buildings.length * 2);
    const seen = new Set();
    for (const m of meshes) {
      const attr = m.geometry.getAttribute('buildingIndex');
      expect(attr.count).toBe(m.geometry.getAttribute('position').count);
      for (let i = 0; i < attr.count; i++) seen.add(attr.getX(i));
    }
    expect([...seen].sort()).toEqual([0, 1, 2]);
  });

  it('buildingIndexAt reads the hit face', () => {
    const meshes = addBuildings({ add() {} }, buildings, null, mat, new Map());
    const ray = new THREE.Raycaster(new THREE.Vector3(35, 100, -5), new THREE.Vector3(0, -1, 0));
    const hit = ray.intersectObjects(meshes, false)[0];
    expect(buildingIndexAt(hit)).toBe(1);
    expect(buildingIndexAt(undefined)).toBeNull();
  });

  it('glowGeometry covers the building a bit above its height', () => {
    const g = glowGeometry(buildings[0]);
    g.computeBoundingBox();
    expect(g.boundingBox.max.y).toBeCloseTo(12.4);
    expect(g.boundingBox.max.x).toBeGreaterThan(10);
  });
});
