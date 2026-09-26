import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { hashPoint } from '../random.js';
import { centroid } from './geom.js';
import { orientedRect, roofTriangles, roofType } from './roofs.js';

const FLAT_CAP_M = 1;

function extrude(footprint, depth, y0) {
  const shape = new THREE.Shape(footprint.map(([x, y]) => new THREE.Vector2(x, y)));
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false });
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, y0, 0);
  return geo;
}

function roofGeometry(tris, y0) {
  const pos = new Float32Array(tris.length * 3);
  tris.forEach(([x, y, z], i) => {
    pos[i * 3] = x;
    pos[i * 3 + 1] = y0 + z;
    pos[i * 3 + 2] = -y;
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.computeVertexNormals();
  return geo;
}

function addMesh(world, geo, material, index, out) {
  const mesh = new THREE.Mesh(geo, material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.userData.buildingIndex = index;
  world.add(mesh);
  out.push(mesh);
}

// highlights: building index -> roof colour of the POI category it houses.
// Returns every building mesh (walls and roofs) tagged with userData.buildingIndex, for hover picking.
export function addBuildings(world, buildings, propertyIndex, mat, highlights = new Map()) {
  const meshes = [];
  buildings.forEach((b, i) => {
    const fp = b.footprint;
    if (!fp || fp.length < 3) return;
    const isProperty = i === propertyIndex;
    const [cx, cy] = centroid(fp);
    const h = hashPoint(cx, cy);
    const wall = isProperty ? PALETTE.propertyWalls
      : b.kind === 'other' ? PALETTE.otherWalls
        : PALETTE.walls[h % PALETTE.walls.length];
    const roof = isProperty ? PALETTE.property
      : highlights.get(i) ?? PALETTE.roofs[(h >>> 4) % PALETTE.roofs.length];
    try {
      const type = roofType(b.kind, fp);
      const wallHeight = type === 'flat' ? Math.max(1, b.height - FLAT_CAP_M) : b.height;
      addMesh(world, extrude(fp, wallHeight, 0), mat(wall), i, meshes);
      if (type === 'flat') {
        addMesh(world, extrude(fp, FLAT_CAP_M, wallHeight), mat(roof), i, meshes);
      } else if (type !== 'none') {
        const tris = roofTriangles(orientedRect(fp), type);
        addMesh(world, roofGeometry(tris, b.height), mat(roof, { flatShading: true, side: THREE.DoubleSide }), i, meshes);
      }
    } catch (err) {
      console.warn('hoodiemap: skipped building', b, err);
    }
  });
  return meshes;
}
