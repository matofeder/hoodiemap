import * as THREE from 'three';

/**
 * Adds all animated objects to the scene.
 * Returns an array of tick(timeSeconds) functions for the render loop.
 */
export function addAnimations(scene, sceneData) {
  const tickers = [];
  const maxDist = (sceneData.display_radius_m || 600) * 1.2;

  tickers.push(..._addTrees(scene, sceneData.trees));
  tickers.push(..._addCars(scene, sceneData.roads, maxDist));
  tickers.push(..._addPedestrians(scene, sceneData.roads, maxDist));
  tickers.push(_addCenterPin(scene));

  return tickers;
}


// ── Trees ────────────────────────────────────────────────────────────────────

function _addTrees(scene, trees) {
  const tickers = [];
  const trunkMat = new THREE.MeshLambertMaterial({ color: 0x7a5c3a });
  const canopyColors = [0x4e8b4e, 0x5a9e5a, 0x639663, 0x4a844a];

  trees.forEach((tree, i) => {
    const h = Math.min(tree.height, 20);
    const r = Math.min(tree.radius, 8);
    const phase = i * 1.3;
    const isConifer = i % 3 === 0;

    const trunkH = h * 0.4;
    const trunkGeo = new THREE.CylinderGeometry(r * 0.12, r * 0.18, trunkH, 6);
    const trunk = new THREE.Mesh(trunkGeo, trunkMat);
    trunk.position.set(tree.x, trunkH / 2, -tree.y);
    trunk.castShadow = true;
    scene.add(trunk);

    const canopyMat = new THREE.MeshLambertMaterial({ color: canopyColors[i % canopyColors.length] });
    let canopy;
    if (isConifer) {
      const canopyGeo = new THREE.ConeGeometry(r * 0.7, h * 0.7, 7);
      canopy = new THREE.Mesh(canopyGeo, canopyMat);
      canopy.position.set(tree.x, trunkH + (h * 0.7) / 2, -tree.y);
    } else {
      const canopyGeo = new THREE.SphereGeometry(r * 0.8, 8, 6);
      canopy = new THREE.Mesh(canopyGeo, canopyMat);
      canopy.position.set(tree.x, trunkH + r * 0.6, -tree.y);
    }
    canopy.castShadow = true;
    scene.add(canopy);

    tickers.push(t => {
      const sway = Math.sin(t * 0.8 + phase) * 0.025;
      canopy.rotation.z = sway;
      trunk.rotation.z = sway * 0.4;
    });
  });

  return tickers;
}


// ── Cars ──────────────────────────────────────────────────────────────────────

const CAR_COLORS = [0xffd93d, 0xff6b6b, 0x4ecdc4, 0xa8e6cf, 0xffeaa7];
const MAJOR_ROAD_TYPES = new Set(['primary', 'secondary', 'tertiary', 'residential']);
const NUM_CARS = 8;

function _makeCar(color) {
  const group = new THREE.Group();
  const bodyGeo = new THREE.BoxGeometry(2.2, 0.8, 4.4);
  const bodyMat = new THREE.MeshLambertMaterial({ color });
  const body = new THREE.Mesh(bodyGeo, bodyMat);
  body.position.y = 0.55;
  body.castShadow = true;
  group.add(body);

  const cabinGeo = new THREE.BoxGeometry(1.8, 0.7, 2.6);
  const cabin = new THREE.Mesh(cabinGeo, bodyMat);
  cabin.position.set(0, 1.25, -0.3);
  cabin.castShadow = true;
  group.add(cabin);

  const wheelGeo = new THREE.CylinderGeometry(0.35, 0.35, 0.25, 8);
  wheelGeo.rotateZ(Math.PI / 2);
  const wheelMat = new THREE.MeshLambertMaterial({ color: 0x222222 });
  [[-1.15, 1.5], [-1.15, -1.5], [1.15, 1.5], [1.15, -1.5]].forEach(([wx, wz]) => {
    const wheel = new THREE.Mesh(wheelGeo, wheelMat);
    wheel.position.set(wx, 0.35, wz);
    group.add(wheel);
  });

  return group;
}

function _buildRoadCurves(roads, maxDist = null) {
  return roads
    .filter(r => MAJOR_ROAD_TYPES.has(r.type) && r.points.length >= 2)
    .filter(r => maxDist == null || r.points.some(([x, y]) => Math.hypot(x, y) <= maxDist))
    .map(r => {
      const pts = r.points.map(([x, y]) => new THREE.Vector3(x, 0.5, -y));
      return new THREE.CatmullRomCurve3(pts);
    })
    .filter(c => c.getLength() > 30);
}

function _addCars(scene, roads, maxDist) {
  const curves = _buildRoadCurves(roads, maxDist);
  if (curves.length === 0) return [];

  const tickers = [];
  for (let i = 0; i < NUM_CARS; i++) {
    const curve = curves[i % curves.length];
    const car = _makeCar(CAR_COLORS[i % CAR_COLORS.length]);
    scene.add(car);

    const baseT = i / NUM_CARS;
    const carSpeed = (2 + Math.random() * 1) / curve.getLength();  // 2-3 m/s on normalized curve

    tickers.push((t) => {
      const tPath = (baseT + t * carSpeed) % 1;
      const pos = curve.getPoint(tPath);
      const tangent = curve.getTangent(tPath);
      car.position.copy(pos);
      car.rotation.y = Math.atan2(tangent.x, tangent.z);
    });
  }

  return tickers;
}


// ── Pedestrians ───────────────────────────────────────────────────────────────

const NUM_PEDESTRIANS = 5;
const PEDESTRIAN_COLORS = [0xffd3b6, 0xffaaa5, 0xa8d8ea, 0xaa96da, 0xfcbad3];

function _makePedestrian(color) {
  const group = new THREE.Group();
  const bodyGeo = new THREE.CapsuleGeometry(0.28, 0.9, 4, 6);
  const mat = new THREE.MeshLambertMaterial({ color });
  const body = new THREE.Mesh(bodyGeo, mat);
  body.position.y = 0.9;
  group.add(body);

  const headGeo = new THREE.SphereGeometry(0.25, 6, 6);
  const head = new THREE.Mesh(headGeo, mat);
  head.position.y = 1.7;
  group.add(head);

  return group;
}

function _offsetCurve(curve, offsetM) {
  const pts = [];
  const n = 20;
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const pos = curve.getPoint(t);
    const tangent = curve.getTangent(t);
    pts.push(new THREE.Vector3(
      pos.x - tangent.z * offsetM,
      pos.y,
      pos.z + tangent.x * offsetM,
    ));
  }
  return new THREE.CatmullRomCurve3(pts);
}

function _addPedestrians(scene, roads, maxDist) {
  const curves = _buildRoadCurves(roads, maxDist);
  if (curves.length === 0) return [];

  const tickers = [];
  for (let i = 0; i < NUM_PEDESTRIANS; i++) {
    const baseCurve = curves[i % curves.length];
    const sidewalk = _offsetCurve(baseCurve, 3.5 + (i % 2) * 1.0);
    const ped = _makePedestrian(PEDESTRIAN_COLORS[i % PEDESTRIAN_COLORS.length]);
    scene.add(ped);

    const baseT = i / NUM_PEDESTRIANS;
    const pedSpeed = (1.0 + Math.random() * 0.5) / sidewalk.getLength();  // 1.0–1.5 m/s walking speed

    tickers.push((t) => {
      const tPath = (baseT + t * pedSpeed) % 1;
      const pos = sidewalk.getPoint(tPath);
      const tangent = sidewalk.getTangent(tPath);
      ped.position.copy(pos);
      ped.rotation.y = Math.atan2(tangent.x, tangent.z);
    });
  }

  return tickers;
}


// ── Center Pin ────────────────────────────────────────────────────────────────

function _addCenterPin(scene) {
  const group = new THREE.Group();
  // SceneJSON coords are UTM-offset from center, so world origin (0,0,0) is the map center.

  const haloGeo = new THREE.RingGeometry(6, 8, 32);
  const haloMat = new THREE.MeshBasicMaterial({ color: 0xe05252, side: THREE.DoubleSide, transparent: true, opacity: 0.4 });
  const halo = new THREE.Mesh(haloGeo, haloMat);
  halo.rotation.x = -Math.PI / 2;
  halo.position.y = 0.3;
  group.add(halo);

  const pinGeo = new THREE.OctahedronGeometry(4, 0);
  const pinMat = new THREE.MeshLambertMaterial({ color: 0xe05252 });
  const pin = new THREE.Mesh(pinGeo, pinMat);
  pin.position.y = 14;
  pin.castShadow = true;
  group.add(pin);

  const stemGeo = new THREE.CylinderGeometry(0.4, 0.4, 14, 6);
  const stemMat = new THREE.MeshLambertMaterial({ color: 0xb03030 });
  const stem = new THREE.Mesh(stemGeo, stemMat);
  stem.position.y = 7;
  group.add(stem);

  scene.add(group);

  return t => {
    const s = 1 + Math.sin(t * 2.5) * 0.1;
    pin.scale.setScalar(s);
    halo.material.opacity = 0.25 + Math.sin(t * 2.5) * 0.15;
    halo.scale.setScalar(1 + Math.sin(t * 1.5) * 0.12);
  };
}


// ── Shrubs ────────────────────────────────────────────────────────────────────

const SHRUB_COLORS = [0x4a7a4a, 0x5a8c3a, 0x3d6e2e, 0x508040];
const MAX_SHRUBS = 200;

export function addShrubs(scene, sceneData) {
  const layers = sceneData.geo_layers;
  if (!layers) return;

  let totalShrubs = 0;
  const SPACING = 8;

  for (const layerName of ['park', 'forest']) {
    const rings = layers[layerName];
    if (!rings) continue;

    for (const ring of rings) {
      if (totalShrubs >= MAX_SHRUBS) return;
      if (!ring || ring.length < 2) continue;

      let accumulated = 0;

      for (let i = 0; i < ring.length - 1; i++) {
        const [x0, y0] = ring[i];
        const [x1, y1] = ring[i + 1];
        const segLen = Math.hypot(x1 - x0, y1 - y0);
        let t = (accumulated === 0) ? 0 : SPACING - accumulated;

        while (t <= segLen) {
          if (totalShrubs >= MAX_SHRUBS) return;
          const frac = t / segLen;
          const sx = x0 + (x1 - x0) * frac;
          const sy = y0 + (y1 - y0) * frac;
          _placeShrub(scene, sx, sy, totalShrubs);
          totalShrubs++;
          t += SPACING;
        }
        accumulated = (accumulated + segLen) % SPACING;
      }
    }
  }
}

function _placeShrub(scene, wx, wy, idx) {
  const clusterCount = 2 + (idx % 3);
  const color = SHRUB_COLORS[idx % SHRUB_COLORS.length];
  const mat = new THREE.MeshLambertMaterial({ color });

  for (let k = 0; k < clusterCount; k++) {
    const angle = (k / clusterCount) * Math.PI * 2 + idx * 0.7;
    const radius = (k === 0) ? 0 : 0.8 + (k * 0.3);
    const r = 0.8 + (k % 2) * 0.4;
    const geo = new THREE.SphereGeometry(r, 6, 5);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(
      wx + Math.cos(angle) * radius,
      r,
      -(wy + Math.sin(angle) * radius),
    );
    mesh.receiveShadow = true;
    scene.add(mesh);
  }
}


// ── Cyclists ─────────────────────────────────────────────────────────────────

const NUM_CYCLISTS = 3;
const CYCLIST_COLORS = [0x3d9970, 0x2980b9, 0xe67e22];

function _makeCyclist(color) {
  const group = new THREE.Group();
  const mat = new THREE.MeshLambertMaterial({ color });

  const bodyGeo = new THREE.BoxGeometry(0.4, 0.8, 1.2);
  const body = new THREE.Mesh(bodyGeo, mat);
  body.position.y = 1.1;
  body.castShadow = true;
  group.add(body);

  const headGeo = new THREE.SphereGeometry(0.22, 6, 6);
  const head = new THREE.Mesh(headGeo, mat);
  head.position.set(0, 1.7, -0.4);
  head.castShadow = true;
  group.add(head);

  const wheelGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.1, 8);
  wheelGeo.rotateZ(Math.PI / 2);
  const wheelMat = new THREE.MeshLambertMaterial({ color: 0x222222 });
  for (const wz of [-0.5, 0.5]) {
    const wheel = new THREE.Mesh(wheelGeo, wheelMat);
    wheel.position.set(0, 0.3, wz);
    group.add(wheel);
  }
  return group;
}

export function addCyclists(scene, roads, maxDist) {
  const curves = _buildRoadCurves(roads, maxDist);
  if (curves.length === 0) return [];
  const tickers = [];
  for (let i = 0; i < NUM_CYCLISTS; i++) {
    const baseCurve = curves[i % curves.length];
    const lane = _offsetCurve(baseCurve, 1.8);
    const cyclist = _makeCyclist(CYCLIST_COLORS[i % CYCLIST_COLORS.length]);
    scene.add(cyclist);
    const baseT = (i + 0.5) / NUM_CYCLISTS;
    const speed = 4 / lane.getLength();
    tickers.push(t => {
      const tPath = (baseT + t * speed) % 1;
      const pos = lane.getPoint(tPath);
      const tangent = lane.getTangent(tPath);
      cyclist.position.copy(pos);
      cyclist.rotation.y = Math.atan2(tangent.x, tangent.z);
    });
  }
  return tickers;
}
