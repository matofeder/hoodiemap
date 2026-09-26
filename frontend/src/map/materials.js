import * as THREE from 'three';

export function createMaterialCache() {
  const cache = new Map();
  return (color, opts = {}) => {
    const key = `${color}|${opts.side ?? ''}|${opts.flatShading ? 1 : 0}`;
    if (!cache.has(key)) cache.set(key, new THREE.MeshLambertMaterial({ color, ...opts }));
    return cache.get(key);
  };
}
