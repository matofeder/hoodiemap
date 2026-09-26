import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { flatGeometry } from './ground.js';
import { ribbonTriangles } from './lines.js';

// Street tier: the street being sold on glows in the property colour under the road surface
// (wider than the road, so a soft band shows on both sides), and the tag sits on the street.
const FOCUS_WIDTH_M = 14;
const LEVEL_Y = 0.058; // just below streets (0.06), above paths and parks

export function addStreetFocus(world, focus, mat) {
  const lines = focus?.lines ?? [];
  const [ax, ay] = focus?.anchor ?? [0, 0];
  const material = new THREE.MeshBasicMaterial({
    color: PALETTE.property, transparent: true, opacity: 0.35, depthWrite: false,
    side: THREE.DoubleSide, clippingPlanes: mat.clippingPlanes,
  });
  if (lines.length) {
    world.add(new THREE.Mesh(flatGeometry(ribbonTriangles(lines, FOCUS_WIDTH_M), LEVEL_Y), material));
  }
  return {
    update(t) {
      material.opacity = 0.28 + Math.sin(t * 2) * 0.1;
    },
    anchor: { x: ax, y: ay, h: 10, base: 0 },
  };
}
