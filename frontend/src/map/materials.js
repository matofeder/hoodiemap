import * as THREE from 'three';

// opts.clip: clip to the map square (for flat layers whose width/caps would poke past the slab edge).
// onCreate: hook applied to every new material (cloud shadows patch the shader there).
export function createMaterialCache(clippingPlanes = [], onCreate = (m) => m) {
  const cache = new Map();
  const mat = (color, { clip = false, ...opts } = {}) => {
    const key = `${color}|${opts.side ?? ''}|${opts.flatShading ? 1 : 0}|${clip ? 1 : 0}`;
    if (!cache.has(key)) {
      cache.set(key, onCreate(new THREE.MeshLambertMaterial({ color, ...opts, ...(clip ? { clippingPlanes } : {}) })));
    }
    return cache.get(key);
  };
  mat.clippingPlanes = clippingPlanes;
  mat.onCreate = onCreate;
  return mat;
}

export function squareClippingPlanes(r) {
  return [
    new THREE.Plane(new THREE.Vector3(-1, 0, 0), r),
    new THREE.Plane(new THREE.Vector3(1, 0, 0), r),
    new THREE.Plane(new THREE.Vector3(0, 0, -1), r),
    new THREE.Plane(new THREE.Vector3(0, 0, 1), r),
  ];
}
