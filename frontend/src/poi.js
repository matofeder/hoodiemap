import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { POI_COLORS, POI_LABELS } from './colors.js';

export function addPOIs(scene, labelRenderer, camera, pois) {
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  const poiMeshes = [];

  pois.forEach(poi => {
    const color = new THREE.Color(POI_COLORS[poi.category] || '#888888');

    // Marker sphere
    const geo = new THREE.SphereGeometry(3.5, 10, 10);
    const mat = new THREE.MeshLambertMaterial({ color });
    const sphere = new THREE.Mesh(geo, mat);
    sphere.position.set(poi.x, 5, -poi.y);
    sphere.castShadow = true;
    sphere.userData.poi = poi;
    scene.add(sphere);
    poiMeshes.push(sphere);

    // Floating name label
    const labelDiv = document.createElement('div');
    labelDiv.className = 'poi-label';
    labelDiv.textContent = poi.name;
    const label = new CSS2DObject(labelDiv);
    label.position.set(0, 5, 0);
    sphere.add(label);

    // Popup (hidden by default)
    const popupDiv = document.createElement('div');
    popupDiv.className = 'poi-popup';
    popupDiv.style.display = 'none';
    const nameEl = document.createElement('div');
    nameEl.className = 'poi-name';
    nameEl.textContent = poi.name;
    const metaEl = document.createElement('div');
    metaEl.className = 'poi-meta';
    metaEl.textContent = `${POI_LABELS[poi.category] || poi.category} · ${poi.distance_m} m`;
    popupDiv.append(nameEl, metaEl);
    const popup = new CSS2DObject(popupDiv);
    popup.position.set(0, 10, 0);
    sphere.add(popup);
    sphere.userData.popup = popupDiv;
  });

  // Click handler — toggle popup on POI click, close on click-elsewhere
  let activePopup = null;

  function onClick(event) {
    const rect = labelRenderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(poiMeshes);

    if (activePopup) {
      activePopup.style.display = 'none';
      activePopup = null;
    }

    if (hits.length > 0) {
      const popup = hits[0].object.userData.popup;
      if (popup) {
        popup.style.display = 'block';
        activePopup = popup;
      }
    }
  }

  labelRenderer.domElement.parentElement.addEventListener('click', onClick);
}
