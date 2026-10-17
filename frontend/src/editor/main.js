import './editor.css';
import { qrPngDataUrl, qrSvg } from '../qr.js';
import { DEFAULT_COORDS, isFixture } from '../url.js';
import { tierLabel } from '../format.js';
import { CONDITIONS, ENERGY_CLASSES, FEATURES, PROPERTY_TYPES, formatDate } from '../presentation/listing.js';
import { dataFromValues, moveItem, validate, valuesFromData } from './form.js';

const $ = (id) => document.getElementById(id);
const form = $('form');
const fixture = isFixture(window.location.search);
const [route, routeId] = window.location.pathname.split('/').filter(Boolean);

const state = {
  pid: route === 'upravit' ? decodeURIComponent(routeId ?? '') : null,
  token: window.location.hash.slice(1) || null,
  location: null,
  photos: [],
};

const SAVE_ERRORS = {
  403: 'Odkaz na úpravy nie je platný. Otvorte ho znova z miesta, kam ste si ho uložili.',
  410: 'Platnosť prezentácie skončila.',
  422: 'Niektoré údaje majú nesprávny tvar. Skontrolujte čísla a e-mail.',
  502: 'Mapu okolia sa teraz nepodarilo načítať z OpenStreetMap. Skúste uložiť znova o minútu.',
};
const FAILED = 'Uloženie zlyhalo. Skontrolujte pripojenie a skúste znova.';

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

// --- browser memory (convenience only: everything works without it) -----------------------

const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
  },
};

function remember(data) {
  const entry = { id: state.pid, token: state.token, title: data.title, label: data.location?.label, at: Date.now() };
  const list = store.get('hm.recent', []).filter((r) => r.id !== state.pid);
  store.set('hm.recent', [entry, ...list].slice(0, 12));
  store.set('hm.agent', data.agent);
}

function renderRecent() {
  const list = store.get('hm.recent', []);
  $('recent').hidden = !list.length;
  $('recent-list').replaceChildren(...list.map((r) => el('li', {}, [
    el('a', { href: `/upravit/${encodeURIComponent(r.id)}#${r.token}`, textContent: r.title || r.label || r.id }),
    el('span', { className: 'ed-muted', textContent: ` · ${r.label ?? ''}` }),
  ])));
}

// --- form fields ---------------------------------------------------------------------------

function fillSelect(id, options) {
  $(id).replaceChildren(el('option', { value: '', textContent: '—' }),
    ...Object.entries(options).map(([value, label]) => el('option', { value, textContent: label })));
}
fillSelect('f-type', PROPERTY_TYPES);
fillSelect('f-condition', CONDITIONS);
fillSelect('f-energy', Object.fromEntries(ENERGY_CLASSES.map((c) => [c, c])));
$('features').replaceChildren(...Object.entries(FEATURES).map(([value, label]) => el('label', { className: 'ed-check' }, [
  el('input', { type: 'checkbox', name: 'features', value, id: `f-feat-${value}` }), ` ${label}`,
])));

function readValues() {
  const values = {};
  for (const node of form.elements) {
    if (!node.name || node.name === 'features') continue;
    values[node.name] = node.value;
  }
  values.features = [...form.querySelectorAll('input[name="features"]:checked')].map((c) => c.value);
  return values;
}

function writeValues(values) {
  for (const [name, value] of Object.entries(values)) {
    if (name === 'features') continue;
    if (form.elements[name]) form.elements[name].value = value;
  }
  for (const c of form.querySelectorAll('input[name="features"]')) c.checked = values.features.includes(c.value);
}

function setLocation(loc) {
  state.location = loc;
  $('address-result').hidden = !loc;
  if (loc) $('address-result').textContent = `${loc.label ?? `${loc.lat.toFixed(5)}, ${loc.lon.toFixed(5)}`} · ${tierLabel(loc.tier)}`;
}

async function findAddress() {
  const q = $('address-q').value.trim();
  if (fixture) {
    setLocation({ ...DEFAULT_COORDS, tier: 'address', name: null, label: q || 'Záhradná, Pezinok' });
    return;
  }
  if (q.length < 2) return;
  $('address-find').disabled = true;
  $('address-result').hidden = false;
  $('address-result').textContent = 'Hľadám…';
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
    if (res.status === 404) {
      $('address-result').textContent = `Nenašli sme „${q}“. Skúste pridať mesto alebo PSČ.`;
      state.location = null;
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const hit = await res.json();
    setLocation({ lat: hit.lat, lon: hit.lon, tier: hit.tier, name: hit.name || null, label: hit.label || null });
    markDirty();
  } catch {
    $('address-result').textContent = 'Vyhľadávanie je dočasne nedostupné, skúste o chvíľu.';
  } finally {
    $('address-find').disabled = false;
  }
}
$('address-find').addEventListener('click', findAddress);
$('address-q').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); findAddress(); }
});

$('f-demo').addEventListener('change', () => { $('demo-detail').hidden = !$('f-demo').checked; });

let dirty = false;
function markDirty() {
  if (!state.pid) return;
  dirty = true;
  $('save-state').textContent = 'Máte neuložené zmeny.';
}
form.addEventListener('input', markDirty);
window.addEventListener('beforeunload', (e) => { if (dirty) e.preventDefault(); });

// --- saving --------------------------------------------------------------------------------

async function call(method, path, body) {
  const headers = { ...(state.token ? { 'X-Edit-Token': state.token } : {}) };
  let payload = body;
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(path, { method, headers, body: payload });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

const apiPath = (suffix = '') => `/api/presentations/${encodeURIComponent(state.pid)}${suffix}`;

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = dataFromValues(readValues(), state.location);
  const problems = validate(data);
  $('problems').replaceChildren(...problems.map((p) => el('li', { textContent: p })));
  $('problems').hidden = !problems.length;
  if (problems.length) return;

  $('save').disabled = true;
  $('save-state').textContent = state.pid ? 'Ukladám…' : 'Vytváram prezentáciu a mapu okolia…';
  try {
    if (state.pid) {
      const updated = await call('PATCH', apiPath(fixture ? '?fixture=true' : ''), data);
      state.photos = updated.data.photos;
    } else {
      const body = { data, fixture };
      if ($('f-demo').checked) {
        body.demo_for = $('f-demo-for').value.trim() || null;
        body.expires_in_days = Number.parseInt($('f-demo-days').value, 10) || 30;
      }
      const created = await call('POST', '/api/presentations', body);
      state.pid = created.id;
      state.token = created.edit_token;
      history.replaceState(null, '', `/upravit/${encodeURIComponent(state.pid)}${fixture ? '?fixture=true' : ''}#${state.token}`);
      await loadExisting();
    }
    remember(data);
    dirty = false;
    $('save-state').textContent = `Uložené o ${new Date().toLocaleTimeString('sk-SK', { hour: '2-digit', minute: '2-digit' })}.`;
  } catch (err) {
    $('save-state').textContent = SAVE_ERRORS[err.status] ?? FAILED;
  } finally {
    $('save').disabled = false;
  }
});

// --- edit mode: share panel, photos, leads -------------------------------------------------

async function loadExisting() {
  const p = await call('GET', apiPath('/edit'));
  writeValues(valuesFromData(p.data));
  setLocation(p.data.location);
  $('address-q').value = p.data.location.label ?? '';
  state.photos = p.data.photos;

  document.title = `${p.data.title || p.data.location.label || 'Prezentácia'} · úpravy · HoodieMap`;
  $('heading').textContent = p.data.title || 'Prezentácia nehnuteľnosti';
  $('subheading').textContent = 'Zmeny uvidia kupujúci po uložení.';
  $('save').textContent = 'Uložiť zmeny';
  $('demo-fields').hidden = true;
  $('recent').hidden = true;

  renderShare(p);
  $('photos-locked').hidden = true;
  $('photos-tools').hidden = false;
  renderPhotos();
  renderLeads(p.leads);
}

async function renderShare(p) {
  const url = `${window.location.origin}/p/${encodeURIComponent(state.pid)}`;
  $('public-url').value = url;
  $('open-url').href = url;
  $('edit-url').value = window.location.href;
  $('share').hidden = false;
  const expiry = [p.demo_for ? `Ukážka pre ${p.demo_for}` : null,
    p.expires_at ? `${p.expired ? 'platnosť skončila' : 'platí do'} ${formatDate(p.expires_at)}` : null].filter(Boolean);
  $('expiry').textContent = expiry.join(' · ');
  $('expiry').hidden = !expiry.length;
  $('qr').innerHTML = await qrSvg(url);
  $('qr-download').href = await qrPngDataUrl(url);
}

function copyButton(buttonId, inputId) {
  $(buttonId).addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($(inputId).value);
    } catch {
      $(inputId).select();
      document.execCommand('copy');
    }
    $(buttonId).textContent = 'Skopírované';
    setTimeout(() => { $(buttonId).textContent = 'Kopírovať'; }, 1500);
  });
}
copyButton('copy-url', 'public-url');
copyButton('copy-edit', 'edit-url');

function renderPhotos() {
  $('photo-list').replaceChildren(...state.photos.map((ph, i) => {
    const caption = el('input', { value: ph.caption ?? '', maxLength: 200, placeholder: 'Popis, napr. Obývačka', id: `cap-${ph.id}` });
    caption.setAttribute('aria-label', `Popis fotky ${i + 1}`);
    caption.addEventListener('change', () => savePhotos(state.photos.map((p) => (p.id === ph.id ? { ...p, caption: caption.value.trim() || null } : p))));
    const up = el('button', { type: 'button', textContent: '↑', disabled: i === 0 });
    up.setAttribute('aria-label', 'Posunúť vyššie');
    up.addEventListener('click', () => savePhotos(moveItem(state.photos, i, -1)));
    const down = el('button', { type: 'button', textContent: '↓', disabled: i === state.photos.length - 1 });
    down.setAttribute('aria-label', 'Posunúť nižšie');
    down.addEventListener('click', () => savePhotos(moveItem(state.photos, i, 1)));
    const del = el('button', { type: 'button', textContent: 'Odstrániť', className: 'ed-del' });
    del.addEventListener('click', () => {
      if (del.dataset.armed) return deletePhoto(ph.id);
      del.dataset.armed = '1';
      del.textContent = 'Naozaj?';
      setTimeout(() => { delete del.dataset.armed; del.textContent = 'Odstrániť'; }, 3000);
    });
    return el('li', { className: 'ed-photo' }, [
      el('img', { src: apiPath(`/photos/${ph.id}/thumb`), alt: '', width: 96, height: 72, loading: 'lazy' }),
      el('div', { className: 'ed-photo-body' }, [caption, el('div', { className: 'ed-photo-tools' }, [up, down, del])]),
    ]);
  }));
}

async function savePhotos(list) {
  const previous = state.photos;
  state.photos = list;
  renderPhotos();
  try {
    const updated = await call('PATCH', apiPath(), { photos: list.map(({ id, caption }) => ({ id, caption })) });
    state.photos = updated.data.photos;
  } catch {
    state.photos = previous;
    $('photo-state').textContent = 'Zmenu fotiek sa nepodarilo uložiť. Skúste znova.';
  }
  renderPhotos();
}

async function deletePhoto(id) {
  try {
    await call('DELETE', apiPath(`/photos/${id}`));
    state.photos = state.photos.filter((p) => p.id !== id);
    renderPhotos();
  } catch {
    $('photo-state').textContent = 'Fotku sa nepodarilo odstrániť. Skúste znova.';
  }
}

$('photo-input').addEventListener('change', async () => {
  const files = [...$('photo-input').files];
  $('photo-input').value = '';
  const failed = [];
  for (const [k, file] of files.entries()) {
    $('photo-state').textContent = `Nahrávam ${k + 1} z ${files.length}…`;
    const body = new FormData();
    body.append('file', file);
    try {
      state.photos = [...state.photos, await call('POST', apiPath('/photos'), body)];
      renderPhotos();
    } catch (err) {
      failed.push(`${file.name}: ${err.status === 422 ? 'nie je fotka vo formáte JPEG, PNG ani WebP, je väčšia ako 15 MB, alebo je fotiek už 40' : 'nahrávanie zlyhalo'}`);
    }
  }
  $('photo-state').textContent = failed.length ? `Nenahrané: ${failed.join('; ')}.` : `Nahrané (${files.length}).`;
});

function renderLeads(leads) {
  $('leads').hidden = false;
  $('lead-count').textContent = leads.length ? String(leads.length) : '';
  $('leads-empty').hidden = leads.length > 0;
  $('lead-list').replaceChildren(...leads.map((l) => el('li', { className: 'ed-lead' }, [
    el('p', {}, [el('strong', { textContent: l.name }),
      el('span', { className: 'ed-muted', textContent: ` · ${new Date(l.created_at).toLocaleString('sk-SK', { dateStyle: 'short', timeStyle: 'short' })}` })]),
    el('p', { className: 'ed-lead-contact' }, [
      ...(l.phone ? [el('a', { href: `tel:${l.phone.replace(/[^\d+]/g, '')}`, textContent: l.phone })] : []),
      ...(l.email ? [el('a', { href: `mailto:${l.email}`, textContent: l.email })] : []),
    ]),
    ...(l.message ? [el('p', { className: 'ed-lead-msg', textContent: l.message })] : []),
  ])));
}
$('leads-refresh').addEventListener('click', async () => {
  try {
    renderLeads((await call('GET', apiPath('/edit'))).leads);
  } catch { /* keep the list on screen */ }
});

// --- start ---------------------------------------------------------------------------------

async function start() {
  if (!state.pid) {
    writeValues(valuesFromData({ agent: store.get('hm.agent', {}) }));
    renderRecent();
    if (fixture) $('address-q').placeholder = 'Režim fixture: adresa sa nevyhľadáva';
    return;
  }
  $('editor').hidden = true;
  $('load-state').hidden = false;
  if (!state.token) {
    $('load-state').textContent = 'Odkaz na úpravy nie je úplný: chýba časť za znakom #. Otvorte ho znova z miesta, kam ste si ho uložili.';
    return;
  }
  $('load-state').textContent = 'Načítavam prezentáciu…';
  try {
    await loadExisting();
    $('load-state').hidden = true;
    $('editor').hidden = false;
  } catch (err) {
    $('load-state').textContent = err.status === 403 ? SAVE_ERRORS[403]
      : err.status === 404 ? 'Túto prezentáciu sme nenašli.' : 'Prezentáciu sa nepodarilo načítať. Skúste obnoviť stránku.';
  }
}
start();
