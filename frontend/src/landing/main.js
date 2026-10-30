import './landing.css';
import { listingUrl, pickVariant, priceLabel, readTags } from './funnel.js';

const $ = (id) => document.getElementById(id);
const session = {
  get(key) { try { return JSON.parse(sessionStorage.getItem(key)); } catch { return null; } },
  set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
};

let info = { open: false, variants: ['9', '19'], operator: null, contact_email: null };
let variant = null;
let tags = { source: null, campaign: null };

function track(kind) {
  if (!variant) return;
  fetch('/api/landing/event', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
    body: JSON.stringify({ kind, variant, ...tags }),
  }).catch(() => {});
}

async function start() {
  try {
    info = await (await fetch('/api/landing')).json();
  } catch { /* keep defaults: the page still reads fine */ }
  const forced = new URLSearchParams(window.location.search).get('cena');
  variant = pickVariant(info.variants, { forced, stored: session.get('hm.variant') });
  session.set('hm.variant', variant);
  tags = readTags(window.location.search, session.get('hm.tags') ?? {});
  session.set('hm.tags', tags);
  document.querySelectorAll('[data-price]').forEach((n) => { n.textContent = priceLabel(variant); });

  if (info.operator) {
    $('operator-line').textContent = `Prevádzkovateľ: ${info.operator}. Otázky a vymazanie údajov: ${info.contact_email}.`;
    $('consent-text').textContent = `Súhlasím, aby ${info.operator} použil môj e-mail na poslanie správy a oznámenie spustenia. Ďalej ho neposkytne; vymazanie na ${info.contact_email}.`;
  }
  $('s-submit').hidden = !info.open;
  $('s-closed').hidden = info.open;

  if (!session.get('hm.viewed')) {
    session.set('hm.viewed', true);
    track('view');
  }
}

// --- the call to action opens the sign-up ---------------------------------------------------

document.querySelectorAll('[data-cta]').forEach((form) => form.addEventListener('submit', (e) => {
  e.preventDefault();
  track('cta');
  const typed = listingUrl(form.querySelector('input').value);
  if (typed) $('s-url').value = typed;
  $('signup-body').hidden = false;
  $('signup-done').hidden = true;
  $('s-error').hidden = true;
  $('signup').showModal();
  $('s-email').focus();
}));

document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => $('signup').close()));
$('signup').addEventListener('click', (e) => { if (e.target === $('signup')) $('signup').close(); });
$('signup-form').addEventListener('input', () => { $('s-error').hidden = true; });

$('signup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = $('s-email').value.trim();
  const problem = !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) ? 'Zadajte e-mail v tvare meno@domena.sk.'
    : !$('s-consent').checked ? 'Bez súhlasu vám správu nemôžeme poslať.' : null;
  if (problem) {
    $('s-error').textContent = problem;
    $('s-error').hidden = false;
    return;
  }
  $('s-submit').disabled = true;
  try {
    const res = await fetch('/api/landing/signup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email, consent: true, variant, ...tags,
        listing_url: listingUrl($('s-url').value),
        timeframe: document.querySelector('input[name="timeframe"]:checked')?.value ?? null,
        website: $('s-website').value,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    $('signup-body').hidden = true;
    $('signup-done').hidden = false;
  } catch {
    $('s-error').textContent = 'Nepodarilo sa to odoslať. Skúste to prosím o chvíľu.';
    $('s-error').hidden = false;
  } finally {
    $('s-submit').disabled = false;
  }
});

start();
