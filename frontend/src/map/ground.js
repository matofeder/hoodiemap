import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { dashSegments, ribbonTriangles } from './lines.js';

const SLAB_THICKNESS = 10;
const ROAD_WIDTH = { main: 9, street: 6, path: 2.5 };
const LEVEL = { forest: 0.02, park: 0.03, water: 0.04, path: 0.05, street: 0.06, main: 0.07, dash: 0.08 };

function flatGeometry(flat, y) {
  const n = flat.length / 2;
  const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    pos[i * 3] = flat[i * 2];
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = -flat[i * 2 + 1];
    nor[i * 3 + 1] = 1;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  return g;
}

function addFlat(world, flat, y, material) {
  if (!flat.length) return;
  const mesh = new THREE.Mesh(flatGeometry(flat, y), material);
  mesh.receiveShadow = true;
  world.add(mesh);
}

export function addGround(world, scene, mat) {
  const r = scene.radius_m;
  const side = mat(PALETTE.slabSide), top = mat(PALETTE.slabTop);
  const slab = new THREE.Mesh(new THREE.BoxGeometry(2 * r, SLAB_THICKNESS, 2 * r), [side, side, top, side, side, side]);
  slab.position.y = -SLAB_THICKNESS / 2;
  slab.receiveShadow = true;
  world.add(slab);

  for (const layer of ['forest', 'park', 'water']) {
    for (const ring of scene.areas?.[layer] ?? []) {
      if (ring.length < 3) continue;
      const shape = new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y)));
      const geo = new THREE.ShapeGeometry(shape);
      geo.rotateX(-Math.PI / 2);
      const mesh = new THREE.Mesh(geo, mat(PALETTE[layer], { side: THREE.DoubleSide }));
      mesh.position.y = LEVEL[layer];
      mesh.receiveShadow = true;
      world.add(mesh);
    }
  }

  const flatMat = (color) => mat(color, { side: THREE.DoubleSide });
  for (const kind of ['path', 'street', 'main']) {
    const lines = scene.roads.filter((rd) => rd.kind === kind).map((rd) => rd.points);
    if (!lines.length) continue;
    const src = kind === 'path' ? lines.flatMap((l) => dashSegments(l, 2, 1.5)) : lines;
    addFlat(world, ribbonTriangles(src, ROAD_WIDTH[kind]), LEVEL[kind], flatMat(kind === 'path' ? PALETTE.path : PALETTE.road));
    if (kind === 'main') {
      addFlat(world, ribbonTriangles(lines.flatMap((l) => dashSegments(l, 4, 5)), 0.5), LEVEL.dash, flatMat(PALETTE.roadDash));
    }
  }
}
