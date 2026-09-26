import './style.css';
import { formatLoadTime, tierLabel } from './format.js';
import { createStage } from './map/stage.js';
import { createRequestGate } from './requestGate.js';
import { DEFAULT_COORDS, getViewFromURL, isFixture, sceneUrl, viewToSearch } from './url.js';

const mapEl = document.getElementById('map');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const retryBtn = document.getElementById('retry');
const statusHint = document.getElementById('status-hint');
const form = document.getElementById('search');
const input = document.getElementById('q');
const searchMsg = document.getElementById('search-msg');
const timingEl = document.getElementById('timing');

const NOT_FOUND = (q) => `Nenašli sme „${q}“. Skúste pridať mesto alebo PSČ.`;
const GEOCODE_DOWN = 'Vyhľadávanie je dočasne nedostupné, skúste o chvíľu.';
const LOAD_FAILED = 'Mapu sa nepodarilo načítať. Skúste to znova o chvíľu.';
const CITY_HINT = ' Mestská úroveň je náročnejšia – skúste konkrétnu ulicu.';
const LOADING = { address: 'Načítavam okolie', street: 'Načítavam ulicu', city: 'Načítavam mesto' };
const FADE_MS = 200; // matches the .gm-status opacity transition
const SLOW_HINT_MS = 8000;

const gate = createRequestGate();
let controller = null;
let stage = null;
let current = null;
// The view actually rendered in `stage` right now (or null before any scene has ever loaded).
// Kept separate from `current` so a search that fails *after* interrupting an in-flight scene
// load can put `current` back on solid ground instead of leaving it pointed at whatever view
// never finished loading.
let displayed = null;

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
  statusHint.hidden = true;
  retryBtn.hidden = !isError;
}

function hideStatus() {
  statusEl.hidden = true;
  statusEl.classList.remove('is-error');
}

// The loading panel is opaque, so once it has faded in the old map is invisible: drop it then
// (frees the WebGL context early and avoids two maps showing through each other).
// Only the stage on screen when loading started is retired: a fast (cached) load may already
// have replaced it with the new map before the timer fires.
function retireStageAfterFade(token) {
  const old = stage;
  if (!old) return;
  setTimeout(() => {
    if (!gate.isCurrent(token) || stage !== old) return;
    old.dispose();
    stage = null;
  }, FADE_MS);
}

// Called when a search interrupts an in-flight scene load and then itself fails (geocode
// 404/503/network error), so the loading overlay that load left behind would otherwise be
// stuck forever. Falls back to the previous map when there is one, or a retryable error when
// there isn't, and stops `current` from pointing at a view that never actually loaded.
function recoverOverlay() {
  if (stage) {
    hideStatus();
  } else {
    showStatus(LOAD_FAILED, true);
  }
  // Only touch current/URL when a newer, never-finished view actually got in between —
  // leave a plain failed search (nothing was interrupted) alone.
  if (displayed && current !== displayed) {
    history.replaceState(null, '', viewToSearch(displayed));
    current = displayed;
  }
}

async function showView(view, startedAt = performance.now()) {
  current = view;
  const { token, signal } = beginRequest();
  showStatus(`${LOADING[view.tier]}${view.label ? ` ${view.label}` : ''}…`, false);
  timingEl.hidden = true;
  retireStageAfterFade(token);
  const hintTimer = setTimeout(() => { if (gate.isCurrent(token)) statusHint.hidden = false; }, SLOW_HINT_MS);
  try {
    const res = await fetch(sceneUrl(view, isFixture(window.location.search)), { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const scene = await res.json();
    if (!gate.isCurrent(token)) return;
    if (view.label) scene.address = `${view.label} · ${tierLabel(view.tier)}`;
    stage?.dispose();
    stage = null;
    stage = createStage(mapEl, scene);
    displayed = view;
    hideStatus();
    timingEl.textContent = formatLoadTime(performance.now() - startedAt, scene.cached === true);
    timingEl.hidden = false;
  } catch (err) {
    if (err.name === 'AbortError' || !gate.isCurrent(token)) return;
    console.error('hoodiemap: scene load failed', err);
    showStatus(LOAD_FAILED + (view.tier === 'city' ? CITY_HINT : ''), true);
  } finally {
    clearTimeout(hintTimer);
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
      recoverOverlay();
      return;
    }
    hit = await res.json();
  } catch (err) {
    if (err.name === 'AbortError' || !gate.isCurrent(token)) return;
    showSearchMsg(GEOCODE_DOWN);
    recoverOverlay();
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
