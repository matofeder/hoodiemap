import * as THREE from 'three';

const GLOW = '#FFFFFF';
const GLOW_INTENSITY = 0.22;
const LABEL_SELECTOR = '.gm-near, .gm-far, .gm-tag';

// Hover (and tap) picking of buildings: the building under the pointer glows softly and the
// tooltip describes it. Labels report their own hover via onLabel, which shares the same state.
export function createHover({ container, camera, meshes, tooltip, describe, requestRender }) {
  const byIndex = new Map();
  for (const m of meshes) {
    const list = byIndex.get(m.userData.buildingIndex) ?? [];
    list.push(m);
    byIndex.set(m.userData.buildingIndex, list);
  }

  const glowCache = new Map();
  const glowing = (material) => {
    if (!glowCache.has(material)) {
      const m = material.clone();
      m.emissive = new THREE.Color(GLOW);
      m.emissiveIntensity = GLOW_INTENSITY;
      m.onBeforeCompile = material.onBeforeCompile;
      m.customProgramCacheKey = material.customProgramCacheKey;
      glowCache.set(material, m);
    }
    return glowCache.get(material);
  };

  let lit = null; // building index currently glowing
  let pinned = false; // touch: keep the tooltip until the next tap
  const originals = new Map();

  function light(index) {
    if (index === lit) return;
    for (const m of byIndex.get(lit) ?? []) m.material = originals.get(m);
    lit = index;
    for (const m of byIndex.get(lit) ?? []) {
      originals.set(m, m.material);
      m.material = glowing(m.material);
    }
    requestRender();
  }

  const raycaster = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(clientX, clientY) {
    const rect = container.getBoundingClientRect();
    ndc.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObjects(meshes, false)[0];
    return { index: hit ? hit.object.userData.buildingIndex : null, x: clientX - rect.left, y: clientY - rect.top };
  }

  function showBuilding(clientX, clientY) {
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

  container.addEventListener('pointermove', onMove);
  container.addEventListener('pointerdown', onDown);
  container.addEventListener('pointerleave', () => { if (!pinned) clear(); });

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

  return { onLabel, clear, dispose() { container.removeEventListener('pointermove', onMove); container.removeEventListener('pointerdown', onDown); } };
}
