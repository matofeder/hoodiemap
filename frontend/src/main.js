import './style.css';
import { createStage } from './map/stage.js';
import { DEFAULT_COORDS, getCoordsFromURL, isFixture } from './url.js';

const mapEl = document.getElementById('map');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const retryBtn = document.getElementById('retry');

function sceneUrl({ lat, lon }, fixture) {
  return `/api/scene?lat=${lat}&lon=${lon}${fixture ? '&fixture=true' : ''}`;
}

async function load() {
  statusEl.hidden = false;
  statusEl.classList.remove('is-error');
  statusText.textContent = 'Načítavam okolie…';
  retryBtn.hidden = true;
  const search = window.location.search;
  const coords = getCoordsFromURL(search) ?? DEFAULT_COORDS;
  try {
    const res = await fetch(sceneUrl(coords, isFixture(search)));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const scene = await res.json();
    createStage(mapEl, scene);
    statusEl.hidden = true;
  } catch (err) {
    console.error('genmap: scene load failed', err);
    statusEl.classList.add('is-error');
    statusText.textContent = 'Mapu sa nepodarilo načítať. Skúste to znova o chvíľu.';
    retryBtn.hidden = false;
  }
}

retryBtn.addEventListener('click', load);
load();
