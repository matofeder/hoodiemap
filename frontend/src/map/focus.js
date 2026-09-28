import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { flatGeometry } from './ground.js';
import { ribbonTriangles } from './lines.js';
import { addPin } from './property.js';

// Street tier: the street being sold on glows in the property colour under the road surface
// (wider than the road, so a soft band shows on both sides), and the same pin and tag as the
// address tier float over the street's midpoint (the exact address is not disclosed).
const FOCUS_WIDTH_M = 14;
const PIN_BASE_M = 8;
const RING_R_M = 12;
const ADDRESS_RADIUS_M = 140; // the pin is sized for the address tier's ±140 m map
const LEVEL_Y = 0.058; // just below streets (0.06), above paths and parks

export function addStreetFocus(world, focus, mat, radius = ADDRESS_RADIUS_M) {
  const lines = focus?.lines ?? [];
  const [ax, ay] = focus?.anchor ?? [0, 0];
  const material = new THREE.MeshBasicMaterial({
    color: PALETTE.property, transparent: true, opacity: 0.35, depthWrite: false,
    side: THREE.DoubleSide, clippingPlanes: mat.clippingPlanes,
  });
  if (lines.length) {
    world.add(new THREE.Mesh(flatGeometry(ribbonTriangles(lines, FOCUS_WIDTH_M), LEVEL_Y), material));
  }
  const size = Math.max(1, radius / ADDRESS_RADIUS_M);
  const pin = addPin(world, ax, ay, PIN_BASE_M * size, RING_R_M * size, mat, size);
  return {
    update(t) {
      material.opacity = 0.28 + Math.sin(t * 2) * 0.1;
      pin.update(t);
    },
    anchor: pin.anchor,
  };
}
