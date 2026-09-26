import * as THREE from 'three';
import { buildingIndexAt, glowGeometry } from './buildings.js';

const LABEL_SELECTOR = '.gm-near, .gm-far, .gm-tag';

// Hover (and tap) picking of buildings: a soft white shell appears over the building under
// the pointer and the tooltip describes it. Labels report their own hover via onLabel.
export function createHover({ container, camera, meshes, world, buildings, tooltip, describe, requestRender }) {
  const glowMat = new THREE.MeshBasicMaterial({ color: '#FFFFFF', transparent: true, opacity: 0.28, depthWrite: false });
  let lit = null; // building index currently glowing
  let glow = null;
  let pinned = false; // touch: keep the tooltip until the next tap
  let disposed = false; // a queued rAF or a stale label event can still fire after teardown

  function light(index) {
    if (disposed || index === lit) return;
    if (glow) {
      world.remove(glow);
      glow.geometry.dispose();
      glow = null;
    }
    lit = index;
    if (lit != null && buildings[lit]) {
      glow = new THREE.Mesh(glowGeometry(buildings[lit]), glowMat);
      glow.renderOrder = 2;
      world.add(glow);
    }
    requestRender();
  }

  const raycaster = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(clientX, clientY) {
    const rect = container.getBoundingClientRect();
    ndc.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    return { index: buildingIndexAt(raycaster.intersectObjects(meshes, false)[0]), x: clientX - rect.left, y: clientY - rect.top };
  }

  function showBuilding(clientX, clientY) {
    if (disposed) return;
    const { index, x, y } = pick(clientX, clientY);
    light(index);
    if (index == null) tooltip.hide();
    else tooltip.show(describe(index), x, y);
  }

  function clear() {
    pinned = false;
    light(null);
    tooltip.hide();
  }

  let queued = null;
  function onMove(e) {
    if (e.pointerType === 'touch' || pinned) return;
    if (e.target.closest?.(LABEL_SELECTOR)) return;
    if (!queued) {
      requestAnimationFrame(() => {
        showBuilding(queued.clientX, queued.clientY);
        queued = null;
      });
    }
    queued = { clientX: e.clientX, clientY: e.clientY };
  }

  function onDown(e) {
    if (e.pointerType !== 'touch' || e.target.closest?.(LABEL_SELECTOR)) return;
    showBuilding(e.clientX, e.clientY);
    pinned = lit != null;
  }

  function onLeave() { if (!pinned) clear(); }

  container.addEventListener('pointermove', onMove);
  container.addEventListener('pointerdown', onDown);
  container.addEventListener('pointerleave', onLeave);

  // Labels: info bubble above the label, and the building they sit on glows too.
  function onLabel(info, buildingIndex, node, touch) {
    if (!info) {
      if (!pinned) clear();
      return;
    }
    const rect = container.getBoundingClientRect(), r = node.getBoundingClientRect();
    light(buildingIndex ?? null);
    tooltip.show(info, r.left + r.width / 2 - rect.left, r.top - rect.top);
    pinned = !!touch;
  }

  return {
    onLabel,
    clear,
    dispose() {
      disposed = true;
      container.removeEventListener('pointermove', onMove);
      container.removeEventListener('pointerdown', onDown);
      container.removeEventListener('pointerleave', onLeave);
      if (glow) {
        world.remove(glow);
        glow.geometry.dispose(); // no light(null): it would render one more frame while tearing down
      }
      glow = null;
      lit = null;
      glowMat.dispose();
    },
  };
}
