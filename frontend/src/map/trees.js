import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { mulberry32, seedFromCoords } from '../random.js';
import { seedTreePositions } from './placement.js';

const TRUNK_H = 3;
const SWAY = 0.04;

export function addTrees(world, scene, mat, { seeded = true } = {}) {
  const rng = mulberry32(seedFromCoords(scene.center.lat, scene.center.lon));
  const pts = seeded ? seedTreePositions(scene, rng) : (scene.trees ?? []).map((t) => [t.x, t.y]);
  const cap = Math.max(1, pts.length);
  const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.45, 0.6, TRUNK_H, 6), mat(PALETTE.trunk), cap);
  const crowns = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 14, 10), mat('#FFFFFF'), cap);
  const m = new THREE.Matrix4(), color = new THREE.Color();
  const trees = pts.map(([x, y], i) => {
    m.makeTranslation(x, TRUNK_H / 2, -y);
    trunks.setMatrixAt(i, m);
    crowns.setColorAt(i, color.set(PALETTE.crowns[i % PALETTE.crowns.length]));
    return { x, y, radius: 2.6 + rng() * 1.9, phase: rng() * Math.PI * 2 };
  });
  trunks.count = crowns.count = pts.length;
  for (const mesh of [trunks, crowns]) {
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    world.add(mesh);
  }

  const q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  function update(t) {
    trees.forEach((tr, i) => {
      const cy = TRUNK_H + tr.radius * 0.8;
      p.set(tr.x + Math.sin(t * 1.3 + tr.phase) * SWAY * cy, cy, -tr.y);
      s.setScalar(tr.radius);
      crowns.setMatrixAt(i, m.compose(p, q, s));
    });
    crowns.instanceMatrix.needsUpdate = true;
  }
  update(0);
  return { update };
}
