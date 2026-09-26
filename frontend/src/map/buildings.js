import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { PALETTE } from '../palette.js';
import { hashPoint } from '../random.js';
import { centroid } from './geom.js';
import { orientedRect, roofTriangles, roofType } from './roofs.js';

const FLAT_CAP_M = 1;
const GLOW_LIFT_M = 0.4;
const GLOW_SCALE = 1.02;

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

// Tag every vertex with its building so a raycast hit on a merged mesh can be traced back.
function tagged(geo, index) {
  geo.deleteAttribute('uv'); // buildings are untextured; merge needs identical attribute sets
  const ids = new Float32Array(geo.getAttribute('position').count).fill(index);
  geo.setAttribute('buildingIndex', new THREE.BufferAttribute(ids, 1));
  return geo;
}

// Returns one mesh per material (all buildings merged), each vertex tagged with buildingIndex.
// Thousands of buildings at the city tier would otherwise mean thousands of draw calls.
export function addBuildings(world, buildings, propertyIndex, mat, highlights = new Map()) {
  const buckets = new Map(); // material -> geometries
  const put = (material, geo) => {
    if (!buckets.has(material)) buckets.set(material, []);
    buckets.get(material).push(geo);
  };
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
      put(mat(wall), tagged(extrude(fp, wallHeight, 0), i));
      if (type === 'flat') {
        put(mat(roof), tagged(extrude(fp, FLAT_CAP_M, wallHeight), i));
      } else if (type !== 'none') {
        const tris = roofTriangles(orientedRect(fp), type);
        put(mat(roof, { flatShading: true, side: THREE.DoubleSide }), tagged(roofGeometry(tris, b.height), i));
      }
    } catch (err) {
      console.warn('hoodiemap: skipped building', b, err);
    }
  });
  const meshes = [];
  for (const [material, geos] of buckets) {
    const mesh = new THREE.Mesh(mergeGeometries(geos, false), material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    world.add(mesh);
    meshes.push(mesh);
    geos.forEach((g) => g.dispose());
  }
  return meshes;
}

export function buildingIndexAt(hit) {
  if (!hit?.face) return null;
  return hit.object.geometry.getAttribute('buildingIndex')?.getX(hit.face.a) ?? null;
}

export function glowGeometry(building) {
  const [cx, cy] = centroid(building.footprint);
  const fp = building.footprint.map(([x, y]) => [cx + (x - cx) * GLOW_SCALE, cy + (y - cy) * GLOW_SCALE]);
  return extrude(fp, building.height + GLOW_LIFT_M, 0);
}
