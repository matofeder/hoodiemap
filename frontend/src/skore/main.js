import './skore.css';
import { SCORES, breakdownTable, emptyFacts, factLine, missingLine } from './facts.js';

const $ = (id) => document.getElementById(id);
const fixture = new URLSearchParams(window.location.search).get('fixture') === 'true';

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function setState(text, isError = false) {
  $('sk-state').textContent = text;
  $('sk-state').classList.toggle('is-error', isError);
}

async function lookup(q) {
  const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
  if (res.status === 404) throw new Error(`Nenašli sme „${q}“. Skúste pridať mesto alebo PSČ.`);
  if (!res.ok) throw new Error('Vyhľadávanie adries je dočasne nedostupné. Skúste o chvíľu.');
  const hit = await res.json();
  return { lat: hit.lat, lon: hit.lon, label: hit.label || q };
}

async function show({ lat, lon, label }) {
  setState(`Počítam skóre pre ${label}… Prvý výpočet môže trvať do minúty.`);
  $('sk-form').querySelector('button').disabled = true;
  try {
    const res = await fetch(`/api/score?lat=${lat}&lon=${lon}${fixture ? '&fixture=true' : ''}`);
    if (!res.ok) throw new Error(res.status === 502 ? 'Mapové dáta sa teraz nepodarilo načítať. Skúste to o minútu.' : 'Skóre sa nepodarilo spočítať.');
    render(await res.json(), label);
    setState('');
    const p = new URLSearchParams({ lat, lon, label });
    if (fixture) p.set('fixture', 'true');
    history.replaceState(null, '', `?${p}`);
  } catch (err) {
    setState(err.message, true);
  } finally {
    $('sk-form').querySelector('button').disabled = false;
  }
}

function render(result, label) {
  $('sk-title').textContent = label;
  $('sk-map').href = `/?lat=${result.lat}&lon=${result.lon}&label=${encodeURIComponent(label)}${fixture ? '&fixture=true' : ''}`;
  $('sk-tiles').replaceChildren(...SCORES.map(({ key, label: name, question }) => {
    const s = result.scores[key];
    const meter = el('div', { className: 'sk-meter' }, [el('i', { style: `width:${s.score}%` })]);
    meter.setAttribute('role', 'img');
    meter.setAttribute('aria-label', `${s.score} zo 100`);
    return el('article', { className: 'sk-tile' }, [
      el('span', { className: 'sk-tile-label' }, [name, ...(s.status ? [el('span', { className: 'sk-badge', textContent: s.status })] : [])]),
      el('span', { className: 'sk-tile-q', textContent: question }),
      el('span', { className: 'sk-tile-value' }, [String(s.score), el('small', { textContent: '/100' })]),
      el('span', { className: 'sk-tile-band', textContent: s.band }),
      meter,
    ]);
  }));
  const t = result.transit;
  $('sk-transit').textContent = t ? `Najbližšia zastávka: ${t.name ?? 'MHD'}, ${factLine(t).detail.replace(`${t.name} · `, '')}. Skóre MHD pridáme, keď napojíme cestovné poriadky.` : '';
  $('sk-details').replaceChildren(...SCORES.map(({ key, label: name }) => {
    const s = result.scores[key];
    const facts = s.facts.map((f) => {
      const line = factLine(f);
      return el('li', {}, [el('span', { textContent: line.title }), el('span', { textContent: line.detail })]);
    });
    const empty = !facts.length && emptyFacts(key);
    const missing = missingLine(key, s.missing);
    return el('section', { className: 'sk-detail' }, [
      el('h3', {}, [name, el('span', { textContent: `${s.score} · ${s.band}` })]),
      ...(facts.length ? [el('ul', { className: 'sk-facts' }, facts)] : []),
      ...(empty ? [el('p', { className: 'sk-muted', textContent: empty })] : []),
      ...(missing ? [el('p', { className: 'sk-missing', textContent: missing })] : []),
      steps(s),
    ]);
  }));
  renderWhoqol(result.whoqol);
  $('sk-result').hidden = false;
}

function renderWhoqol(w) {
  $('sk-facets').replaceChildren(...w.facets.map((f) => {
    const meter = el('div', { className: 'sk-meter' }, [el('i', { style: `width:${f.score ?? 0}%` })]);
    meter.setAttribute('role', 'img');
    meter.setAttribute('aria-label', f.score == null ? 'chýbajú dáta' : `${f.score} zo 100`);
    const detail = f.score == null
      ? `Chýbajú dáta. Plán: ${f.planned}.`
      : f.breakdown.map((r) => `${r.label} ${Math.round(r.sub_score)}`).join(' · ');
    return el('div', { className: `sk-facet${f.score == null ? ' is-empty' : ''}` }, [
      el('span', { className: 'sk-facet-id', textContent: f.id }),
      el('span', { className: 'sk-facet-label' }, [f.label, ...(f.status && f.score != null ? [el('span', { className: 'sk-badge', textContent: f.status })] : [])]),
      el('span', { className: 'sk-facet-score', textContent: f.score == null ? '–' : String(f.score) }),
      meter,
      el('span', { className: 'sk-facet-detail', textContent: detail }),
    ]);
  }));
  $('sk-index').textContent = w.index == null
    ? `Index prostredia zatiaľ nepočítame: máme dáta pre ${w.facets_with_data} z ${w.facets_total} aspektov a WHOQOL-BREF počíta oblasť len pri aspoň ${w.min_facets}.`
    : `Index prostredia: ${w.index} (priemer ${w.facets_with_data} aspektov).`;
}

function steps(s) {
  const t = breakdownTable(s);
  const tr = (cells, tag = 'td') => el('tr', {}, cells.map((c) => el(tag, { textContent: c })));
  const body = [
    ...(t.start ? [tr([t.start, '', '', '', '100'])] : []),
    ...t.rows.map((r) => tr([r.label, r.fact, r.sub, r.weight, r.points])),
  ];
  const table = el('table', { className: 'sk-steps' }, [
    el('thead', {}, [tr(t.head, 'th')]),
    el('tbody', {}, body),
    el('tfoot', {}, [tr(['Skóre', '', '', '', t.total])]),
  ]);
  return el('details', { className: 'sk-steps-box' }, [
    el('summary', { textContent: 'Výpočet krok za krokom' }),
    el('div', { className: 'sk-steps-wrap' }, [table]),
    el('p', { className: 'sk-muted', textContent: t.note }),
  ]);
}

async function loadMethod() {
  try {
    const m = await (await fetch('/api/score/method')).json();
    const sections = [
      ['Pešo', 'Za každú kategóriu (potraviny, reštaurácie, kaviarne, obchody, banka, park, škola, lekáreň, kultúra a šport) dostane adresa body podľa vzdialenosti. Do 5 minút chôdze plné, potom menej, po 30 minútach nič.', m.walk.source],
      ['Chôdza', `Vzdušnú vzdialenosť násobíme ${String(m.walking.detour).replace('.', ',')}, aby zodpovedala ceste po uliciach, a rátame ${m.walking.m_per_min} m za minútu.`, m.walking.source],
      ['Zeleň', `Tri časti: verejná zeleň aspoň ${String(m.green.min_ha).replace('.', ',')} ha do 300 m, podiel zelene do ${m.green.cover_radius_m} m (cieľ ${Math.round(m.green.cover_target * 100)} %) a les alebo veľký park do 1 km. Váhy: ${m.green.weights.source}.`, m.green.source],
      ['Rodina', 'Materská a základná škola, ihrisko, lekár, potraviny a skóre Zeleň. Vzdialenosti hodnotíme rovnakou krivkou chôdze ako pri Pešo. Váhy: ' + m.family.weights.source + '.', m.family.source],
      ['Pokoj (orientačné)', 'Od 100 odpočítavame body za blízkosť diaľnice, ciest I. až III. triedy, železnice, električky a barov do 150 m.', m.quiet.source],
    ];
    $('sk-method-body').replaceChildren(
      ...sections.flatMap(([title, what, source]) => [el('h3', { textContent: title }), el('p', { textContent: `${what} Zdroj: ${source}` })]),
      el('p', { textContent: `${m.data} Verzia metodiky ${m.version}.` }),
    );
  } catch {
    $('sk-method-body').replaceChildren(el('p', { textContent: 'Metodiku sa nepodarilo načítať.' }));
  }
}

$('sk-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = $('sk-q').value.trim();
  if (q.length < 2) return setState('Zadajte adresu, ulicu alebo obec.', true);
  try {
    await show(await lookup(q));
  } catch (err) {
    setState(err.message, true);
  }
});
document.querySelectorAll('.sk-examples button').forEach((b) => b.addEventListener('click', () => {
  $('sk-q').value = b.dataset.label;
  show({ lat: Number(b.dataset.lat), lon: Number(b.dataset.lon), label: b.dataset.label });
}));

loadMethod();
const p = new URLSearchParams(window.location.search);
if (p.get('lat') && p.get('lon')) {
  $('sk-q').value = p.get('label') ?? '';
  show({ lat: Number(p.get('lat')), lon: Number(p.get('lon')), label: p.get('label') ?? 'Vybraná adresa' });
}
