import { initFrame } from './frame.js';
import { showRouteHint, hideRouteHint } from './route.js';
import { POI_COLORS } from './colors.js';

export function getMode(pathname = window.location.pathname, search = window.location.search) {
  const params = new URLSearchParams(search);
  if (pathname.startsWith('/embed')) return 'embed';
  if (pathname.startsWith('/view/')) return 'view';
  return params.get('mode') || 'demo';
}

export function getCoordsFromURL(search = window.location.search) {
  const params = new URLSearchParams(search);
  const lat = parseFloat(params.get('lat'));
  const lon = parseFloat(params.get('lon'));
  if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
  return null;
}

async function fetchScene(lat, lon) {
  const res = await fetch(`/api/scene?lat=${lat}&lon=${lon}`);
  if (!res.ok) throw new Error(`Scene fetch failed: ${res.status}`);
  return res.json();
}

async function init() {
  const mode = getMode();
  document.body.dataset.mode = mode;
  const coordsFromURL = getCoordsFromURL();

  if (mode === 'embed' || mode === 'view') {
    if (!coordsFromURL) {
      document.getElementById('loading-text').textContent = 'Chýbajú koordináty (lat/lon).';
      return;
    }
    const sceneData = await fetchScene(coordsFromURL.lat, coordsFromURL.lon);
    const { createScene } = await import('./scene.js');
    const container = document.getElementById('threejs-mount');
    const { scene: embedScene, needleController: embedNeedles } = createScene(container, sceneData, mode);
    if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
      const center = sceneData.center;
      const frameContainer = document.getElementById('canvas-container');
      initFrame(
        frameContainer,
        sceneData.outer_pois,
        center.lat,
        center.lon,
        (poi) => {
          const color = POI_COLORS[poi.category] || '#888888';
          if (embedNeedles) embedNeedles.highlight(poi);
          showRouteHint(embedScene, center.lat, center.lon, poi.lat, poi.lon, color);
        },
        (poi) => {
          if (embedNeedles) embedNeedles.highlight(null);
          hideRouteHint(embedScene);
        },
      );
    }
    document.getElementById('loading').style.display = 'none';
    return;
  }

  // Demo mode
  const { initDemoUI } = await import('./ui.js');
  const { createScene } = await import('./scene.js');

  let frameCtrl = null;
  initDemoUI(async (lat, lon, displayName) => {
    document.getElementById('loading').style.display = 'flex';
    document.getElementById('loading-text').textContent = 'Načítavam mapu…';
    try {
      const sceneData = await fetchScene(lat, lon);
      const container = document.getElementById('threejs-mount');
      const frameContainer = document.getElementById('canvas-container');

      // Tear down previous frame before creating new scene
      if (frameCtrl) { frameCtrl.clear(); frameCtrl = null; }

      const { scene, needleController } = createScene(container, sceneData, 'demo');

      // Render outer POI indicators
      if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
        const center = sceneData.center;
        frameCtrl = initFrame(
          frameContainer,
          sceneData.outer_pois,
          center.lat,
          center.lon,
          // onHover
          (poi, el) => {
            const color = POI_COLORS[poi.category] || '#888888';
            if (needleController) needleController.highlight(poi);
            // Show info card
            const card = document.getElementById('outer-poi-info-card');
            const rect = el.getBoundingClientRect();
            const containerRect = frameContainer.getBoundingClientRect();
            card.style.left = `${rect.left - containerRect.left + rect.width / 2}px`;
            card.style.top = `${rect.top - containerRect.top - 10}px`;
            card.style.transform = 'translate(-50%, -100%)';
            document.getElementById('opc-name').textContent = poi.name;
            document.getElementById('opc-meta').textContent =
              `${poi.category} · ${poi.distance_m >= 1000 ? (poi.distance_m / 1000).toFixed(1) + ' km' : poi.distance_m + ' m'}`;
            card.classList.add('visible');
            showRouteHint(scene, center.lat, center.lon, poi.lat, poi.lon, color);
          },
          // onLeave
          (poi, el) => {
            if (needleController) needleController.highlight(null);
            document.getElementById('outer-poi-info-card').classList.remove('visible');
            hideRouteHint(scene);
          },
        );
      }
      document.getElementById('info-address').textContent = displayName;
      const top3 = sceneData.pois.slice(0, 3).map(p => `${p.name} ${p.distance_m}m`).join(' · ');
      document.getElementById('info-pois').textContent = top3;
      document.getElementById('info-card').style.display = 'block';
      document.getElementById('embed-btn').style.display = 'block';
      const shareInput = document.getElementById('share-url');
      if (shareInput) {
        fetch(`/api/scene/share?lat=${lat}&lon=${lon}`)
          .then(r => r.json())
          .then(share => { shareInput.value = `${window.location.origin}${share.view_url}`; })
          .catch(() => {});
      }
      const embedSrc = `${window.location.origin}/embed?lat=${lat}&lon=${lon}`;
      document.getElementById('embed-code').value =
        `<iframe src="${embedSrc}" width="100%" height="500" allow="fullscreen" style="border:none;border-radius:8px"></iframe>`;
    } finally {
      document.getElementById('loading').style.display = 'none';
    }
  });

  document.getElementById('embed-btn').addEventListener('click', () => {
    document.getElementById('embed-modal').style.display = 'flex';
  });
  document.getElementById('modal-close').addEventListener('click', () => {
    document.getElementById('embed-modal').style.display = 'none';
  });

  document.getElementById('loading').style.display = 'none';
}

if (typeof document !== 'undefined') {
  init().catch(err => {
    document.getElementById('loading-text').textContent = `Chyba: ${err.message}`;
    document.getElementById('loading-spinner').style.display = 'none';
  });
}
