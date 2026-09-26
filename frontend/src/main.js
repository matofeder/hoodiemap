import './style.css';
import { formatLoadTime, tierLabel } from './format.js';
import { createStage } from './map/stage.js';
import { createRequestGate } from './requestGate.js';
import { DEFAULT_COORDS, getViewFromURL, isFixture, sceneUrl, viewToSearch } from './url.js';

const mapEl = document.getElementById('map');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const retryBtn = document.getElementById('retry');
const form = document.getElementById('search');
const input = document.getElementById('q');
const searchMsg = document.getElementById('search-msg');
const timingEl = document.getElementById('timing');

const NOT_FOUND = (q) => `Nenašli sme „${q}“. Skúste pridať mesto alebo PSČ.`;
const GEOCODE_DOWN = 'Vyhľadávanie je dočasne nedostupné, skúste o chvíľu.';
const LOAD_FAILED = 'Mapu sa nepodarilo načítať. Skúste to znova o chvíľu.';
const CITY_HINT = ' Mestská úroveň je náročnejšia – skúste konkrétnu ulicu.';
const LOADING = { address: 'Načítavam okolie', street: 'Načítavam ulicu', city: 'Načítavam mesto' };

const gate = createRequestGate();
let controller = null;
let stage = null;
let current = null;

function defaultView() {
  return { ...DEFAULT_COORDS, tier: 'address', name: null, label: null };
}

function beginRequest() {
  controller?.abort();
  controller = new AbortController();
  return { token: gate.next(), signal: controller.signal };
}

function showStatus(text, isError) {
  statusEl.hidden = false;
  statusEl.classList.toggle('is-error', isError);
  statusText.textContent = text;
  retryBtn.hidden = !isError;
}

async function showView(view, startedAt = performance.now()) {
  current = view;
  const { token, signal } = beginRequest();
  showStatus(`${LOADING[view.tier]}${view.label ? ` ${view.label}` : ''}…`, false);
  try {
    const res = await fetch(sceneUrl(view, isFixture(window.location.search)), { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const scene = await res.json();
    if (!gate.isCurrent(token)) return;
    if (view.label) scene.address = `${view.label} · ${tierLabel(view.tier)}`;
    stage?.dispose();
    stage = createStage(mapEl, scene);
    statusEl.hidden = true;
    timingEl.textContent = formatLoadTime(performance.now() - startedAt, scene.cached === true);
    timingEl.hidden = false;
  } catch (err) {
    if (err.name === 'AbortError' || !gate.isCurrent(token)) return;
    console.error('hoodiemap: scene load failed', err);
    showStatus(LOAD_FAILED + (view.tier === 'city' ? CITY_HINT : ''), true);
  }
}

function showSearchMsg(text) {
  searchMsg.textContent = text;
  searchMsg.hidden = false;
}

async function search(q) {
  const startedAt = performance.now();
  const { token, signal } = beginRequest();
  searchMsg.hidden = true;
  let hit;
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`, { signal });
    if (!gate.isCurrent(token)) return;
    if (!res.ok) {
      showSearchMsg(res.status === 404 ? NOT_FOUND(q) : GEOCODE_DOWN);
      return;
    }
    hit = await res.json();
  } catch (err) {
    if (err.name !== 'AbortError' && gate.isCurrent(token)) showSearchMsg(GEOCODE_DOWN);
    return;
  }
  const view = { lat: hit.lat, lon: hit.lon, tier: hit.tier, name: hit.name || null, label: hit.label || null };
  history.pushState(null, '', viewToSearch(view));
  await showView(view, startedAt);
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (q.length >= 2) search(q);
});
retryBtn.addEventListener('click', () => showView(current ?? defaultView()));
window.addEventListener('popstate', () => {
  const view = getViewFromURL(window.location.search) ?? defaultView();
  input.value = view.label ?? '';
  showView(view);
});

const initial = getViewFromURL(window.location.search) ?? defaultView();
input.value = initial.label ?? '';
showView(initial);
