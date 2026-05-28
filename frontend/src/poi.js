import * as THREE from 'three';
import { POI_COLORS } from './colors.js';

export function addPOIMarkers(scene, pois) {
  pois.forEach(poi => {
    const color = new THREE.Color(POI_COLORS[poi.category] || '#888888');
    const geo = new THREE.SphereGeometry(3.5, 10, 10);
    const mat = new THREE.MeshLambertMaterial({ color });
    const sphere = new THREE.Mesh(geo, mat);
    sphere.position.set(poi.x, 5, -poi.y);
    sphere.castShadow = true;
    scene.add(sphere);
  });
}
