import './editor.css';
import { qrPngDataUrl, qrSvg } from '../qr.js';
import { DEFAULT_COORDS, isFixture } from '../url.js';
import { tierLabel } from '../format.js';
import { CONDITIONS, ENERGY_CLASSES, FEATURES, PROPERTY_TYPES, formatDate } from '../presentation/listing.js';
import { dataFromValues, mergeDraft, moveItem, validate, valuesFromData } from './form.js';

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
  create403: 'Admin token nesedí. Prezentácie na tomto serveri vytvára len správca.',
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

async function call(method, path, body, extraHeaders = {}) {
  const headers = { ...(state.token ? { 'X-Edit-Token': state.token } : {}), ...extraHeaders };
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
      const admin = $('f-admin').value;
      if (admin) store.set('hm.admin', admin);
      const created = await call('POST', '/api/presentations', body, admin ? { 'X-Admin-Token': admin } : {});
      state.pid = created.id;
      state.token = created.edit_token;
      history.replaceState(null, '', `/upravit/${encodeURIComponent(state.pid)}${fixture ? '?fixture=true' : ''}#${state.token}`);
      await loadExisting();
    }
    remember(data);
    dirty = false;
    $('save-state').textContent = `Uložené o ${new Date().toLocaleTimeString('sk-SK', { hour: '2-digit', minute: '2-digit' })}.`;
  } catch (err) {
    const key = !state.pid && err.status === 403 ? 'create403' : err.status;
    $('save-state').textContent = SAVE_ERRORS[key] ?? FAILED;
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
  setupAi(p.ai);
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
  $('source').hidden = !p.source_url;
  if (p.source_url) $('source-link').href = p.source_url;
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

// --- voice and AI draft --------------------------------------------------------------------

const AI_ERRORS = {
  413: 'Nahrávka je príliš dlhá. Nahrajte kratšie časti.',
  422: 'Nie je z čoho písať: nahrajte alebo napíšte poznámky.',
  503: 'AI nie je na tomto serveri nastavená.',
  502: 'Služba AI teraz neodpovedala. Skúste to o chvíľu.',
};
const MAX_RECORDING_S = 10 * 60;
let ai = { voice: false, text: false };

function setupAi(features) {
  ai = features ?? ai;
  $('ai-fields').hidden = !ai.voice && !ai.text;
  $('ai-locked').hidden = true;
  $('ai-tools').hidden = false;
  $('ai-voice').hidden = !ai.voice;
  $('ai-draft').textContent = ai.text ? 'Pripraviť návrh inzerátu' : 'Vložiť poznámky do popisu';
}

function aiState(text) {
  $('ai-state').textContent = text;
}

let recorder = null;
let recTimer = 0;

function recordingType() {
  const types = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'];
  return types.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) ?? '';
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    aiState('Nahrávanie v tomto prehliadači nefunguje. Nahrajte zvukový súbor, napríklad z diktafónu v mobile.');
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    aiState('Prehliadač nedovolil použiť mikrofón. Povoľte ho v nastaveniach stránky alebo nahrajte zvukový súbor.');
    return;
  }
  const type = recordingType();
  const chunks = [];
  recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  recorder.addEventListener('dataavailable', (e) => { if (e.data.size) chunks.push(e.data); });
  recorder.addEventListener('stop', () => {
    stream.getTracks().forEach((t) => t.stop());
    const mime = recorder.mimeType || type || 'audio/webm';
    recorder = null;
    const ext = mime.includes('mp4') ? 'm4a' : mime.includes('ogg') ? 'ogg' : 'webm';
    transcribeAudio(new File(chunks, `poznamky.${ext}`, { type: mime.split(';')[0] }));
  });
  recorder.start(1000);
  const started = Date.now();
  $('rec').setAttribute('aria-pressed', 'true');
  $('rec').textContent = 'Zastaviť';
  aiState('Nahrávam… Hovorte prirodzene, po skončení kliknite na Zastaviť.');
  recTimer = setInterval(() => {
    const s = Math.floor((Date.now() - started) / 1000);
    $('rec-time').textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
    if (s >= MAX_RECORDING_S) stopRecording();
  }, 250);
}

function stopRecording() {
  if (recorder?.state !== 'recording') return;
  clearInterval(recTimer);
  $('rec').setAttribute('aria-pressed', 'false');
  $('rec').textContent = 'Nahrávať';
  recorder?.stop();
}

$('rec').addEventListener('click', () => (recorder ? stopRecording() : startRecording()));
$('audio-file').addEventListener('change', () => {
  const file = $('audio-file').files[0];
  $('audio-file').value = '';
  if (file) transcribeAudio(file);
});

async function transcribeAudio(file) {
  $('rec').disabled = true;
  aiState('Prepisujem nahrávku… Dlhšia nahrávka môže trvať aj minútu.');
  const body = new FormData();
  body.append('file', file);
  try {
    const { text } = await call('POST', apiPath('/ai/transcribe'), body);
    const box = $('ai-transcript');
    box.value = [box.value.trim(), text].filter(Boolean).join('\n\n');
    aiState(text ? 'Prepis je hotový. Skontrolujte ho a pripravte návrh.' : 'V nahrávke sme nepočuli reč. Skúste to znova bližšie pri mikrofóne.');
  } catch (err) {
    aiState(AI_ERRORS[err.status] ?? 'Prepis zlyhal. Skúste to znova.');
  } finally {
    $('rec').disabled = false;
  }
}

function highlight(changed) {
  form.querySelectorAll('.ed-ai-filled').forEach((n) => n.classList.remove('ed-ai-filled'));
  for (const name of changed) {
    const node = name.startsWith('feature:')
      ? form.querySelector(`#f-feat-${name.slice(8)}`)?.closest('label')
      : form.elements[name];
    if (!node) continue;
    node.classList.add('ed-ai-filled');
    node.addEventListener('input', () => node.classList.remove('ed-ai-filled'), { once: true });
  }
}

$('ai-draft').addEventListener('click', async () => {
  const transcript = $('ai-transcript').value.trim();
  if (!ai.text) {
    if (!transcript) return aiState(AI_ERRORS[422]);
    const desc = form.elements.description;
    desc.value = [desc.value.trim(), transcript].filter(Boolean).join('\n\n');
    highlight(['description']);
    markDirty();
    return aiState('Poznámky sú v popise. Upravte ich a uložte.');
  }
  $('ai-draft').disabled = true;
  $('ai-missing').hidden = true;
  aiState('Pripravujem návrh inzerátu…');
  try {
    const values = readValues();
    const draft = await call('POST', apiPath('/ai/draft'), {
      transcript: transcript || null, data: dataFromValues(values, state.location),
    });
    const { values: next, changed } = mergeDraft(values, draft);
    writeValues(next);
    highlight(changed);
    if (changed.length) markDirty();
    $('ai-missing-list').replaceChildren(...draft.missing.map((m) => el('li', { textContent: m })));
    $('ai-missing').hidden = !draft.missing.length;
    aiState(changed.length
      ? `Návrh doplnil ${changed.length} ${changed.length === 1 ? 'pole' : changed.length < 5 ? 'polia' : 'polí'} (zvýraznené). Skontrolujte ich a uložte.`
      : 'Návrh nič nové nedoplnil.');
  } catch (err) {
    aiState(AI_ERRORS[err.status] ?? 'Návrh sa nepodarilo pripraviť. Skúste to znova.');
  } finally {
    $('ai-draft').disabled = false;
  }
});

// --- start ---------------------------------------------------------------------------------

async function start() {
  if (!state.pid) {
    writeValues(valuesFromData({ agent: store.get('hm.agent', {}) }));
    fetch('/api/features').then((r) => r.json()).then(({ ai: f, create_needs_admin: needsAdmin }) => {
      if (state.pid) return;
      $('admin-fields').hidden = !needsAdmin;
      $('f-admin').value = store.get('hm.admin', '');
      if (!f.voice && !f.text) return;
      $('ai-fields').hidden = false;
      $('ai-tools').hidden = true;
      $('ai-locked').hidden = false;
    }).catch(() => {});
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
