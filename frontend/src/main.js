import { initInfographic } from './infographic.js';
import { createScene } from './scene.js';

const DEFAULT_LAT = 48.28646434486518;
const DEFAULT_LON = 17.27221245956356;

export function getCoordsFromURL(search = window.location.search) {
  const params = new URLSearchParams(search);
  const lat = parseFloat(params.get('lat'));
  const lon = parseFloat(params.get('lon'));
  if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
  return null;
}

async function fetchScene(lat, lon) {
  const useFixture = new URLSearchParams(window.location.search).get('fixture') === 'true';
  const url = useFixture
    ? `/api/scene?lat=${lat}&lon=${lon}&fixture=true`
    : `/api/scene?lat=${lat}&lon=${lon}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Scene fetch failed: ${res.status}`);
  return res.json();
}

async function init() {
  const coords = getCoordsFromURL() || { lat: DEFAULT_LAT, lon: DEFAULT_LON };
  const appEl = document.getElementById('app');

  try {
    const sceneData = await fetchScene(coords.lat, coords.lon);
    const { canvasSlot } = initInfographic(appEl, sceneData);
    createScene(canvasSlot, sceneData);
    document.getElementById('loading').style.display = 'none';
  } catch (err) {
    document.getElementById('loading').textContent = `Chyba: ${err.message}`;
  }
}

init();
