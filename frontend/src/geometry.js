import * as THREE from 'three';

/**
 * Builds a flat ribbon BufferGeometry following a CatmullRomCurve3.
 * The ribbon lies at y = 0.15.
 *
 * @param {THREE.CatmullRomCurve3} curve
 * @param {number} width  — full width in metres
 * @param {number} segmentsPerMetre — geometry density (default 0.5 = one segment per 2m)
 * @returns {THREE.BufferGeometry}
 */
export function buildRibbonGeometry(curve, width, segmentsPerMetre = 0.5) {
  const length = curve.getLength();
  const numSegments = Math.max(4, Math.ceil(length * segmentsPerMetre));
  const half = width / 2;

  const positions = [];
  const indices = [];

  for (let i = 0; i <= numSegments; i++) {
    const t = i / numSegments;
    const pos = curve.getPoint(t);
    const tan = curve.getTangent(t).normalize();
    // Perpendicular in XZ plane (y is up)
    const px = -tan.z * half;
    const pz =  tan.x * half;
    positions.push(pos.x - px, 0.15, pos.z - pz); // left
    positions.push(pos.x + px, 0.15, pos.z + pz); // right
  }

  for (let i = 0; i < numSegments; i++) {
    const a = i * 2, b = i * 2 + 1, c = i * 2 + 2, d = i * 2 + 3;
    indices.push(a, b, d,  a, d, c);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals();
  return geo;
}

/**
 * Builds a flat dashed line BufferGeometry following a CatmullRomCurve3.
 * Used for road centre markings.
 *
 * @param {THREE.CatmullRomCurve3} curve
 * @param {number} dashLength  — metres per dash
 * @param {number} gapLength   — metres between dashes
 * @param {number} yOffset     — world y to place the geometry at
 * @param {number} dashWidth   — width of each dash stripe
 * @returns {THREE.BufferGeometry}
 */
export function buildDashLineGeometry(curve, dashLength = 2, gapLength = 3, yOffset = 0.17, dashWidth = 0.25) {
  const totalLength = curve.getLength();
  const period = dashLength + gapLength;
  const positions = [];

  let d = 0;
  while (d < totalLength) {
    const t0 = d / totalLength;
    const t1 = Math.min((d + dashLength) / totalLength, 1);
    const tm = (t0 + t1) / 2;

    const p0 = curve.getPoint(t0);
    const p1 = curve.getPoint(t1);
    const tan = curve.getTangent(tm).normalize();
    const hw = dashWidth / 2;
    const px = -tan.z * hw;
    const pz =  tan.x * hw;

    // Two triangles forming a dash quad
    positions.push(
      p0.x - px, yOffset, p0.z - pz,
      p0.x + px, yOffset, p0.z + pz,
      p1.x + px, yOffset, p1.z + pz,

      p0.x - px, yOffset, p0.z - pz,
      p1.x + px, yOffset, p1.z + pz,
      p1.x - px, yOffset, p1.z - pz,
    );
    d += period;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();
  return geo;
}
