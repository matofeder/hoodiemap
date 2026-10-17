import '../style.css';
import './presentation.css';
import { createStage } from '../map/stage.js';
import { qrSvg } from '../qr.js';
import {
  featureLabels, formatDate, formatPrice, keyFacts, localityRows, paragraphs, paramRows,
} from './listing.js';

const $ = (id) => document.getElementById(id);
const pid = decodeURIComponent(window.location.pathname.split('/').filter(Boolean)[1] ?? '');
const api = `/api/presentations/${encodeURIComponent(pid)}`;
const photoUrl = (photo, size) => `${api}/photos/${photo.id}/${size}`;

const MESSAGES = {
  404: 'Túto prezentáciu sme nenašli. Skontrolujte odkaz.',
  410: 'Platnosť tejto ukážky skončila. O novú požiadajte makléra.',
  failed: 'Prezentáciu sa nepodarilo načítať. Skúste to znova o chvíľu.',
};

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

async function load() {
  $('state').hidden = false;
  $('state-text').textContent = 'Načítavam prezentáciu…';
  $('state-retry').hidden = true;
  let res;
  try {
    res = await fetch(api);
  } catch {
    return showError(MESSAGES.failed, true);
  }
  if (res.status === 404 || res.status === 410) return showError(MESSAGES[res.status], false);
  if (!res.ok) return showError(MESSAGES.failed, true);
  render(await res.json());
}

function showError(text, retry) {
  $('state-text').textContent = text;
  $('state-retry').hidden = !retry;
  $('state').classList.add('is-error');
}

function render(p) {
  const d = p.data;
  const label = d.location.label ?? p.scene.address ?? '';
  document.title = [d.title, label].filter(Boolean).join(' · ') || 'Prezentácia nehnuteľnosti';

  if (p.demo_for) {
    $('demo').textContent = `Ukážka pre ${p.demo_for}${p.expires_at ? ` · platí do ${formatDate(p.expires_at)}` : ''}`;
    $('demo').hidden = false;
  }
  $('address').textContent = label;
  $('title').textContent = d.title || label || 'Nehnuteľnosť';
  $('facts').replaceChildren(...keyFacts(d.params).map((f) => el('li', { textContent: f })));
  $('price').textContent = formatPrice(d.price_eur, d.offer);
  if (d.price_note) {
    $('price-note').textContent = d.price_note;
    $('price-note').hidden = false;
  }

  renderGallery(d.photos);

  const paras = paragraphs(d.description);
  $('description').replaceChildren(...paras.map((t) => el('p', { textContent: t })));
  $('about').hidden = !paras.length;

  const rows = paramRows(d.params);
  $('params').replaceChildren(...rows.map((r) => el('div', {}, [el('dt', { textContent: r.label }), el('dd', { textContent: r.value })])));
  const features = featureLabels(d.params.features);
  $('features').replaceChildren(...features.map((f) => el('li', { textContent: f })));
  $('params-section').hidden = !rows.length && !features.length;

  renderAgent(d.agent);
  renderLocality(p.scene);
  lazyMap(p.scene);
  qrSvg(window.location.origin + window.location.pathname).then((svg) => { $('qr').innerHTML = svg; });

  $('state').hidden = true;
  $('page').hidden = false;
}

// --- gallery -------------------------------------------------------------------------------

let photos = [];
let shown = 0;

function renderGallery(list) {
  photos = list;
  $('gallery').hidden = !photos.length;
  if (!photos.length) return;
  $('gallery-thumbs').replaceChildren(...photos.map((ph, i) => {
    const b = el('button', { type: 'button', className: 'pr-thumb' },
      [el('img', { src: photoUrl(ph, 'thumb'), alt: '', loading: 'lazy', width: 160, height: 120 })]);
    b.setAttribute('aria-label', ph.caption || `Fotografia ${i + 1}`);
    b.addEventListener('click', () => showPhoto(i));
    return b;
  }));
  $('gallery-thumbs').hidden = photos.length < 2;
  showPhoto(0);
}

function showPhoto(i) {
  shown = (i + photos.length) % photos.length;
  const ph = photos[shown];
  Object.assign($('gallery-img'), { src: photoUrl(ph, 'large'), alt: ph.caption || '', width: ph.w, height: ph.h });
  $('gallery-count').textContent = photos.length > 1 ? `${shown + 1} / ${photos.length}` : '';
  [...$('gallery-thumbs').children].forEach((t, k) => t.setAttribute('aria-current', String(k === shown)));
  if ($('viewer').open) fillViewer();
}

function fillViewer() {
  const ph = photos[shown];
  Object.assign($('viewer-img'), { src: photoUrl(ph, 'large'), alt: ph.caption || '' });
  $('viewer-caption').textContent = [ph.caption, photos.length > 1 ? `${shown + 1} / ${photos.length}` : ''].filter(Boolean).join(' · ');
  $('viewer-prev').hidden = $('viewer-next').hidden = photos.length < 2;
}

$('gallery-main').addEventListener('click', () => {
  fillViewer();
  $('viewer').showModal();
});
$('viewer-prev').addEventListener('click', () => showPhoto(shown - 1));
$('viewer-next').addEventListener('click', () => showPhoto(shown + 1));
$('viewer-close').addEventListener('click', () => $('viewer').close());
$('viewer').addEventListener('click', (e) => { if (e.target === $('viewer')) $('viewer').close(); });
$('viewer').addEventListener('keydown', (e) => {
  if (e.key === 'ArrowLeft') showPhoto(shown - 1);
  if (e.key === 'ArrowRight') showPhoto(shown + 1);
});
let swipeX = null;
$('viewer').addEventListener('pointerdown', (e) => { swipeX = e.clientX; });
$('viewer').addEventListener('pointerup', (e) => {
  if (swipeX == null) return;
  const dx = e.clientX - swipeX;
  swipeX = null;
  if (Math.abs(dx) > 50) showPhoto(shown + (dx < 0 ? 1 : -1));
});

// --- agent and contact ---------------------------------------------------------------------

function renderAgent(agent = {}) {
  const parts = [];
  if (agent.name) parts.push(el('p', { className: 'pr-agent-name', textContent: agent.name }));
  if (agent.agency) parts.push(el('p', { className: 'pr-muted', textContent: agent.agency }));
  if (agent.phone) parts.push(el('a', { href: `tel:${agent.phone.replace(/[^\d+]/g, '')}`, textContent: agent.phone }));
  if (agent.email) parts.push(el('a', { href: `mailto:${agent.email}`, textContent: agent.email }));
  $('agent').replaceChildren(...parts);
  $('agent').hidden = !parts.length;
}

$('lead-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.currentTarget;
  const body = {
    name: f.name.value.trim(), email: f.email.value.trim(), phone: f.phone.value.trim(),
    message: f.message.value.trim(), consent: f.consent.checked, website: f.website.value,
  };
  const problem = !body.name ? 'Vyplňte meno.'
    : !body.email && !body.phone ? 'Zadajte e-mail alebo telefón, aby sa vám maklér mohol ozvať.'
      : !body.consent ? 'Na odoslanie potrebujeme váš súhlas so spracovaním údajov.' : null;
  if (problem) return formError(problem);
  $('lead-submit').disabled = true;
  try {
    const res = await fetch(`${api}/leads`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (res.status === 422) return formError('Skontrolujte e-mail a telefón, niektorý z nich nemá správny tvar.');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    f.hidden = true;
    $('lead-done').hidden = false;
  } catch {
    formError('Správu sa nepodarilo odoslať. Skúste to znova o chvíľu.');
  } finally {
    $('lead-submit').disabled = false;
  }
});

function formError(text) {
  $('lead-error').textContent = text;
  $('lead-error').hidden = false;
}

// --- neighbourhood -------------------------------------------------------------------------

function renderLocality(scene) {
  const rows = localityRows(scene);
  $('locality').tBodies[0].replaceChildren(...rows.map((r) => el('tr', {}, [
    el('td', {}, [
      el('span', { className: 'pr-dot', style: `background:${r.color}` }),
      el('span', { className: 'pr-loc-label', textContent: r.label }),
      ...(r.name ? [el('span', { className: 'pr-loc-name', textContent: r.name })] : []),
    ]),
    el('td', { className: 'pr-num', textContent: r.distance }),
    el('td', { className: 'pr-num pr-muted', textContent: r.time }),
  ])));
}

// The WebGL map is the heaviest part of the page: build it only when it is about to scroll in.
function lazyMap(scene) {
  const mapEl = $('map');
  const io = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    io.disconnect();
    createStage(mapEl, scene);
  }, { rootMargin: '400px' });
  io.observe(mapEl);
}

$('state-retry').addEventListener('click', load);
load();
