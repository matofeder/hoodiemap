export function getMode() {
  const params = new URLSearchParams(window.location.search);
  const path = window.location.pathname;
  if (path.startsWith('/embed')) return 'embed';
  if (path.startsWith('/view/')) return 'view';
  return params.get('mode') || 'demo';
}

export function getCoordsFromURL() {
  const params = new URLSearchParams(window.location.search);
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
  const coordsFromURL = getCoordsFromURL();

  if (mode === 'embed' || mode === 'view') {
    if (!coordsFromURL) {
      document.getElementById('loading').textContent = 'Chýbajú koordináty (lat/lon).';
      return;
    }
    const sceneData = await fetchScene(coordsFromURL.lat, coordsFromURL.lon);
    const { createScene } = await import('./scene.js');
    const container = document.getElementById('canvas-container');
    createScene(container, sceneData, mode);
    document.getElementById('loading').style.display = 'none';
    return;
  }

  // Demo mode
  const { initDemoUI } = await import('./ui.js');
  const { createScene } = await import('./scene.js');

  initDemoUI(async (lat, lon, displayName) => {
    document.getElementById('loading').style.display = 'flex';
    document.getElementById('loading').textContent = 'Načítavam mapu…';
    try {
      const sceneData = await fetchScene(lat, lon);
      const container = document.getElementById('canvas-container');
      createScene(container, sceneData, 'demo');
      document.getElementById('info-address').textContent = displayName;
      const top3 = sceneData.pois.slice(0, 3).map(p => `${p.name} ${p.distance_m}m`).join(' · ');
      document.getElementById('info-pois').textContent = top3;
      document.getElementById('info-card').style.display = 'block';
      document.getElementById('embed-btn').style.display = 'block';
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

init().catch(err => {
  document.getElementById('loading').textContent = `Chyba: ${err.message}`;
});
