import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { centroid } from './geom.js';
import { orientedRect } from './roofs.js';

const PIN_CLEARANCE = 12;
const PIN_SCALE = 1.7;

export function addProperty(world, scene, mat) {
  const idx = scene.property?.building_index;
  const b = idx != null ? scene.buildings[idx] : null;
  const [x, y] = b ? centroid(b.footprint) : [0, 0];
  const ringR = b ? Math.max(12, orientedRect(b.footprint).length / 2 + 5) : 12;
  const base = (b?.height ?? 0) + PIN_CLEARANCE;

  const pinMat = mat(PALETTE.property);
  const pin = new THREE.Group();
  const head = new THREE.Mesh(new THREE.SphereGeometry(3.2, 20, 14), pinMat);
  head.position.y = 5;
  const tip = new THREE.Mesh(new THREE.ConeGeometry(2.3, 5.5, 20), pinMat);
  tip.rotation.x = Math.PI;
  tip.position.y = 1.2;
  const dot = new THREE.Mesh(new THREE.SphereGeometry(1.3, 12, 8), mat('#FFFFFF'));
  dot.position.set(0, 5, 2.6);
  pin.add(head, tip, dot);
  pin.scale.setScalar(PIN_SCALE);
  pin.traverse((o) => { o.castShadow = true; });
  world.add(pin);

  const ringGeo = new THREE.RingGeometry(ringR, ringR + 2, 48);
  ringGeo.rotateX(-Math.PI / 2);
  const ringMat = new THREE.MeshBasicMaterial({ color: PALETTE.property, transparent: true, depthWrite: false });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.position.set(x, 0.2, -y);
  world.add(ring);

  function update(t) {
    pin.position.set(x, base + Math.sin(t * 2.4) * 1.6, -y);
    pin.rotation.y = t * 1.2;
    const p = (t * 0.45) % 1;
    ring.scale.setScalar(0.7 + p * 1.1);
    ringMat.opacity = 0.75 * (1 - p);
  }
  update(0);
  return { update, anchor: { x, y, h: base + 9 * PIN_SCALE } };
}
