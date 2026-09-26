import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { planStreetDecor, planTerraces } from './placement.js';

// Street furniture is exaggerated like the people, otherwise it is invisible at widget scale.
const DECOR_SCALE = 1.8;

const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
const at = (x, y, z, sx = 1, sy = 1, sz = 1) =>
  new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), new THREE.Quaternion(), new THREE.Vector3(sx, sy, sz));

// Each model faces local +x. Parts: [geometry, colour | null (per-instance palette), local matrix].
const MODELS = {
  bench: [
    [box(0.5, 0.1, 1.6), PALETTE.wood, at(0, 0.45, 0)],
    [box(0.08, 0.45, 1.6), PALETTE.wood, at(-0.22, 0.75, 0)],
    [box(0.4, 0.4, 0.1), PALETTE.metal, at(0, 0.2, 0.65)],
    [box(0.4, 0.4, 0.1), PALETTE.metal, at(0, 0.2, -0.65)],
  ],
  lamp: [
    [new THREE.CylinderGeometry(0.06, 0.09, 3.2, 6), PALETTE.metal, at(0, 1.6, 0)],
    [new THREE.SphereGeometry(0.24, 10, 8), PALETTE.lampGlow, at(0, 3.3, 0)],
  ],
  planter: [
    [box(1.1, 0.5, 1.1), PALETTE.terracotta, at(0, 0.25, 0)],
    [new THREE.SphereGeometry(0.55, 10, 8), null, at(0, 0.62, 0, 1, 0.6, 1)],
  ],
  table: [
    [new THREE.CylinderGeometry(0.45, 0.45, 0.06, 12), '#FFFFFF', at(0, 0.75, 0)],
    [new THREE.CylinderGeometry(0.04, 0.04, 2.1, 5), PALETTE.metal, at(0, 1.05, 0)],
    [new THREE.ConeGeometry(1.15, 0.45, 8), null, at(0, 2.15, 0)],
    [box(0.38, 0.45, 0.38), PALETTE.wood, at(0.75, 0.22, 0)],
    [box(0.38, 0.45, 0.38), PALETTE.wood, at(-0.75, 0.22, 0)],
  ],
};
const INSTANCE_COLORS = { planter: PALETTE.flowers, table: PALETTE.parasols };

function addModel(world, kind, items, mat) {
  if (!items.length) return;
  const base = new THREE.Matrix4(), m = new THREE.Matrix4(), q = new THREE.Quaternion(), color = new THREE.Color();
  const up = new THREE.Vector3(0, 1, 0), scale = new THREE.Vector3().setScalar(DECOR_SCALE);
  for (const [geo, fixed, local] of MODELS[kind]) {
    const mesh = new THREE.InstancedMesh(geo, mat(fixed ?? '#FFFFFF', { clip: true }), items.length);
    items.forEach((it, i) => {
      base.compose(new THREE.Vector3(it.x, 0.06, -it.y), q.setFromAxisAngle(up, it.angle ?? 0), scale);
      mesh.setMatrixAt(i, m.multiplyMatrices(base, local));
      if (!fixed) {
        const palette = INSTANCE_COLORS[kind];
        mesh.setColorAt(i, color.set(palette[i % palette.length]));
      }
    });
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    world.add(mesh);
  }
}

export function addDecor(world, scene, mat) {
  const decor = planStreetDecor(scene);
  for (const kind of ['bench', 'lamp', 'planter']) addModel(world, kind, decor.filter((d) => d.kind === kind), mat);
  addModel(world, 'table', planTerraces(scene), mat);
}
