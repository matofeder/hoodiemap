import '../skore/skore.css';
import './porovnanie.css';
import { MAX_ADDRESSES, buildTable, parseAddresses, placeLine, serializeAddresses } from './compare.js';

const $ = (id) => document.getElementById(id);
const fixture = new URLSearchParams(window.location.search).get('fixture') === 'true';
const EXAMPLES = [
  { lat: 48.28646434486518, lon: 17.27221245956356, label: 'Záhradná, Pezinok' },
  { lat: 48.2967070, lon: 17.2784455, label: 'Veltlínska 2, Pezinok' },
  { lat: 48.2714954, lon: 17.3017308, label: 'Viničné' },
  { lat: 48.1450720, lon: 17.1121379, label: 'Námestie SNP, Bratislava' },
];

let addresses = parseAddresses(window.location.search);
const cache = new Map();   // "lat,lon" -> score result

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function setState(text, isError = false) {
  $('cmp-state').textContent = text;
  $('cmp-state').classList.toggle('is-error', isError);
}

async function lookup(q) {
  const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
  if (res.status === 404) throw new Error(`Nenašli sme „${q}“. Skúste pridať mesto alebo PSČ.`);
  if (!res.ok) throw new Error('Vyhľadávanie adries je dočasne nedostupné. Skúste o chvíľu.');
  const hit = await res.json();
  return { lat: hit.lat, lon: hit.lon, label: hit.label || q };
}

async function score({ lat, lon }) {
  const key = `${lat},${lon}`;
  if (!cache.has(key)) {
    const res = await fetch(`/api/score?lat=${lat}&lon=${lon}${fixture ? '&fixture=true' : ''}`);
    if (!res.ok) throw new Error(res.status === 502 ? 'Mapové dáta sa teraz nepodarilo načítať. Skúste to o minútu.' : 'Skóre sa nepodarilo spočítať.');
    cache.set(key, await res.json());
  }
  return cache.get(key);
}

const scoreLink = ({ lat, lon, label }) => {
  const p = new URLSearchParams({ lat, lon, label });
  if (fixture) p.set('fixture', 'true');
  return `/skore?${p}`;
};

async function update() {
  history.replaceState(null, '', addresses.length ? serializeAddresses(addresses, fixture) : (fixture ? '?fixture=true' : window.location.pathname));
  $('cmp-form').querySelector('button').disabled = addresses.length >= MAX_ADDRESSES;
  if (!addresses.length) {
    $('cmp-result').hidden = true;
    return;
  }
  setState(`Počítam ${addresses.length === 1 ? 'adresu' : `${addresses.length} adresy`}… Prvý výpočet môže trvať do minúty.`);
  try {
    const results = await Promise.all(addresses.map(score));
    render(results);
    setState(addresses.length === 1 ? 'Pridajte aspoň jednu ďalšiu adresu na porovnanie.' : '');
  } catch (err) {
    setState(err.message, true);
  }
}

function cell(c, { muted = false } = {}) {
  if (c.value == null) return el('td', { className: 'cmp-cell is-empty', textContent: '–', title: 'chýbajú dáta' });
  const bar = el('span', { className: 'cmp-bar' }, [el('i', { style: `width:${c.value}%` })]);
  const td = el('td', { className: `cmp-cell${c.best ? ' is-best' : ''}${muted ? ' is-sub' : ''}` }, [
    el('span', { className: 'cmp-num', textContent: String(c.value) }), bar,
  ]);
  if (c.fact) td.append(el('span', { className: 'cmp-fact', textContent: c.fact.split(';')[0] }));
  return td;
}

function label(r, { toggle = null } = {}) {
  const name = [r.label, ...(r.status ? [el('span', { className: 'sk-badge', textContent: r.status })] : [])];
  const head = toggle
    ? el('button', { type: 'button', className: 'cmp-toggle', ariaExpanded: 'false' }, [el('span', { className: 'cmp-label' }, name)])
    : el('span', { className: 'cmp-label' }, name);
  const th = el('th', { scope: 'row' }, [head]);
  if (r.note) th.append(el('span', { className: 'cmp-note', textContent: r.note }));
  return th;
}

function render(results) {
  const cols = addresses.length;
  const header = el('tr', {}, [
    el('td', { className: 'cmp-corner' }),
    ...addresses.map((a, i) => el('th', { scope: 'col', className: 'cmp-col' }, [
      el('span', { className: 'cmp-col-name', textContent: a.label }),
      el('span', { className: 'cmp-note', textContent: placeLine(results[i].region) }),
      el('span', { className: 'cmp-col-links' }, [
        el('a', { href: scoreLink(a), textContent: 'Výpočet ↗' }),
        el('button', { type: 'button', className: 'cmp-remove', textContent: 'Odobrať', ariaLabel: `Odobrať ${a.label}`,
          onclick: () => { addresses = addresses.filter((_, j) => j !== i); update(); } }),
      ]),
    ])),
  ]);
  const table = buildTable(results);
  $('cmp-planned').textContent = table.planned.length ? ` Pripravujeme oblasti: ${table.planned.join(', ')}; do indexu zatiaľ nevstupujú.` : '';
  const bodies = table.flatMap((section) => {
    const title = el('tbody', { className: 'cmp-section' }, [el('tr', {}, [el('th', { colSpan: cols + 1, scope: 'colgroup', textContent: section.title })])]);
    return [title, ...section.rows.map((r) => {
      const subs = (r.indicators ?? []).map((ind) => el('tr', { className: 'cmp-ind', hidden: true }, [
        el('th', { scope: 'row' }, [el('span', { className: 'cmp-label', textContent: ind.label }),
          ...(ind.shared ? [el('span', { className: 'cmp-note', textContent: 'rovnaká hodnota pre všetky adresy: ide o štatistiku celého územia' })] : [])]),
        ...ind.cells.map((c) => cell(c, { muted: true })),
      ]));
      const main = el('tr', { className: r.id === 'index' ? 'cmp-row is-index' : 'cmp-row' }, [label(r, { toggle: subs.length ? true : null }), ...r.cells.map((c) => cell(c))]);
      const btn = main.querySelector('.cmp-toggle');
      if (btn) {
        btn.addEventListener('click', () => {
          const open = btn.getAttribute('aria-expanded') !== 'true';
          btn.setAttribute('aria-expanded', String(open));
          subs.forEach((s) => { s.hidden = !open; });
        });
      }
      return el('tbody', {}, [main, ...subs]);
    })];
  });
  $('cmp-table').replaceChildren(el('thead', {}, [header]), ...bodies);
  $('cmp-result').hidden = false;
}

async function add(point) {
  if (addresses.length >= MAX_ADDRESSES) return setState(`Porovnať sa dá najviac ${MAX_ADDRESSES} adries.`, true);
  if (addresses.some((a) => a.lat === point.lat && a.lon === point.lon)) return setState('Táto adresa už v porovnaní je.', true);
  addresses = [...addresses, point];
  await update();
}

$('cmp-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = $('cmp-q').value.trim();
  if (q.length < 2) return setState('Zadajte adresu, ulicu alebo obec.', true);
  try {
    await add(await lookup(q));
    $('cmp-q').value = '';
  } catch (err) {
    setState(err.message, true);
  }
});
document.querySelectorAll('.sk-examples button').forEach((b) => b.addEventListener('click', () => {
  addresses = b.dataset.set === 'all' ? EXAMPLES : EXAMPLES.slice(0, 3);
  update();
}));
$('cmp-share').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(window.location.href);
    $('cmp-share').textContent = 'Odkaz skopírovaný';
  } catch {
    $('cmp-share').textContent = 'Skopírujte adresu z prehliadača';
  }
  setTimeout(() => { $('cmp-share').textContent = 'Kopírovať odkaz'; }, 2500);
});

update();
