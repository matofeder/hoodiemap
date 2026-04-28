import * as THREE from 'three';

/**
 * Adds all animated objects to the scene.
 * Returns an array of tick(timeSeconds) functions for the render loop.
 */
export function addAnimations(scene, sceneData) {
  const tickers = [];

  tickers.push(..._addTrees(scene, sceneData.trees));
  tickers.push(..._addCars(scene, sceneData.roads));
  tickers.push(..._addPedestrians(scene, sceneData.roads));
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

    const trunkH = h * 0.4;
    const trunkGeo = new THREE.CylinderGeometry(r * 0.12, r * 0.18, trunkH, 6);
    const trunk = new THREE.Mesh(trunkGeo, trunkMat);
    trunk.position.set(tree.x, trunkH / 2, -tree.y);
    trunk.castShadow = true;
    scene.add(trunk);

    const canopyMat = new THREE.MeshLambertMaterial({ color: canopyColors[i % canopyColors.length] });
    const canopyGeo = new THREE.ConeGeometry(r * 0.7, h * 0.7, 7);
    const canopy = new THREE.Mesh(canopyGeo, canopyMat);
    canopy.position.set(tree.x, trunkH + (h * 0.7) / 2, -tree.y);
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
const NUM_CARS = 4;

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

function _buildRoadCurves(roads) {
  return roads
    .filter(r => MAJOR_ROAD_TYPES.has(r.type) && r.points.length >= 2)
    .map(r => {
      const pts = r.points.map(([x, y]) => new THREE.Vector3(x, 0.2, -y));
      return new THREE.CatmullRomCurve3(pts);
    })
    .filter(c => c.getLength() > 30);
}

function _addCars(scene, roads) {
  const curves = _buildRoadCurves(roads);
  if (curves.length === 0) return [];

  const tickers = [];
  for (let i = 0; i < NUM_CARS; i++) {
    const curve = curves[i % curves.length];
    const car = _makeCar(CAR_COLORS[i % CAR_COLORS.length]);
    scene.add(car);

    let t = i / NUM_CARS;
    const speed = 0.012 + Math.random() * 0.008;
    const curveLen = curve.getLength();

    tickers.push(() => {
      t = (t + speed * (1 / curveLen) * 16) % 1;
      const pos = curve.getPoint(t);
      const tangent = curve.getTangent(t);
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
  const bodyGeo = new THREE.CapsuleGeometry(0.22, 0.7, 4, 6);
  const mat = new THREE.MeshLambertMaterial({ color });
  const body = new THREE.Mesh(bodyGeo, mat);
  body.position.y = 0.9;
  group.add(body);

  const headGeo = new THREE.SphereGeometry(0.2, 6, 6);
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

function _addPedestrians(scene, roads) {
  const curves = _buildRoadCurves(roads);
  if (curves.length === 0) return [];

  const tickers = [];
  for (let i = 0; i < NUM_PEDESTRIANS; i++) {
    const baseCurve = curves[i % curves.length];
    const sidewalk = _offsetCurve(baseCurve, 2.5 + (i % 2) * 1.5);
    const ped = _makePedestrian(PEDESTRIAN_COLORS[i % PEDESTRIAN_COLORS.length]);
    scene.add(ped);

    let t = i / NUM_PEDESTRIANS;
    const speed = 0.003 + Math.random() * 0.002;
    const curveLen = sidewalk.getLength();

    tickers.push(() => {
      t = (t + speed * (1 / curveLen) * 16) % 1;
      const pos = sidewalk.getPoint(t);
      const tangent = sidewalk.getTangent(t);
      ped.position.copy(pos);
      ped.rotation.y = Math.atan2(tangent.x, tangent.z);
    });
  }

  return tickers;
}


// ── Center Pin ────────────────────────────────────────────────────────────────

function _addCenterPin(scene) {
  const group = new THREE.Group();

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
