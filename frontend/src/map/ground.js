import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { dashSegments, offsetLines, ribbonTriangles } from './lines.js';
import { pavingTexture } from './textures.js';

const SLAB_THICKNESS = 10;
const ROAD_WIDTH = { main: 9, street: 6, path: 2.5, pedestrian: 10 };
const LEVEL = { forest: 0.02, park: 0.03, water: 0.04, plaza: 0.045, path: 0.05, pedestrian: 0.055, street: 0.06, main: 0.07, mark: 0.08 };
// Lane markings: dashed centre line [width, dash, gap]; main roads also get solid edge lines.
const CENTRE_LINE = { main: [0.5, 3, 3], street: [0.35, 1.8, 2.6] };
const EDGE_LINE_W = 0.35;

export function flatGeometry(flat, y) {
  const n = flat.length / 2;
  const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), uv = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) {
    uv[i * 2] = flat[i * 2];
    uv[i * 2 + 1] = flat[i * 2 + 1];
    pos[i * 3] = flat[i * 2];
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = -flat[i * 2 + 1];
    nor[i * 3 + 1] = 1;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return g;
}

function addFlat(world, flat, y, material) {
  if (!flat.length) return;
  const mesh = new THREE.Mesh(flatGeometry(flat, y), material);
  mesh.receiveShadow = true;
  world.add(mesh);
}

export function addGround(world, scene, mat, { lanes = true } = {}) {
  const r = scene.radius_m;
  const side = mat(PALETTE.slabSide), top = mat(PALETTE.slabTop);
  // Only the top receives shadows — building shadows falling over the slab sides look like dirt.
  const slab = new THREE.Mesh(new THREE.BoxGeometry(2 * r, SLAB_THICKNESS, 2 * r), [side, side, top, side, side, side]);
  slab.position.y = -SLAB_THICKNESS / 2;
  world.add(slab);
  const surface = new THREE.Mesh(new THREE.PlaneGeometry(2 * r, 2 * r).rotateX(-Math.PI / 2), top);
  surface.position.y = 0.01;
  surface.receiveShadow = true;
  world.add(surface);

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

  // Pedestrian zones: warm stone paving, as squares (areas) and as wide ways (lines).
  const paving = mat.onCreate(new THREE.MeshLambertMaterial({ map: pavingTexture(), side: THREE.DoubleSide, clippingPlanes: mat.clippingPlanes }));
  for (const ring of scene.areas?.plaza ?? []) {
    if (ring.length < 3) continue;
    const geo = new THREE.ShapeGeometry(new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y))));
    geo.rotateX(-Math.PI / 2);
    const mesh = new THREE.Mesh(geo, paving);
    mesh.position.y = LEVEL.plaza;
    mesh.receiveShadow = true;
    world.add(mesh);
  }
  const zone = scene.roads.filter((rd) => rd.kind === 'pedestrian').map((rd) => rd.points);
  if (zone.length) addFlat(world, ribbonTriangles(zone, ROAD_WIDTH.pedestrian), LEVEL.pedestrian, paving);

  const flatMat = (color) => mat(color, { side: THREE.DoubleSide, clip: true });
  for (const kind of ['path', 'street', 'main']) {
    const lines = scene.roads.filter((rd) => rd.kind === kind).map((rd) => rd.points);
    if (!lines.length) continue;
    const src = kind === 'path' ? lines.flatMap((l) => dashSegments(l, 2, 1.5)) : lines;
    addFlat(world, ribbonTriangles(src, ROAD_WIDTH[kind]), LEVEL[kind], flatMat(kind === 'path' ? PALETTE.path : PALETTE.road));
    if (lanes) {
      const centre = CENTRE_LINE[kind];
      if (!centre) continue;
      const [w, on, off] = centre;
      const mark = flatMat(PALETTE.laneMark);
      addFlat(world, ribbonTriangles(lines.flatMap((l) => dashSegments(l, on, off)), w), LEVEL.mark, mark);
      if (kind === 'main') {
        const edges = lines.flatMap((l) => offsetLines(l, ROAD_WIDTH.main / 2 - 0.9));
        addFlat(world, ribbonTriangles(edges, EDGE_LINE_W), LEVEL.mark, mark);
      }
    }
  }
}
