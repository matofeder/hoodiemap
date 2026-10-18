import '../editor/editor.css';
import './ahp.css';
import { POSITIONS, formatCr, judgmentFor, positionLabel, worstPair } from './judgments.js';

const $ = (id) => document.getElementById(id);
function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

let config = null;
const answers = {};   // set_id -> { "A|B": position }
const results = {};   // set_id -> last /check result

$('a-code').value = new URLSearchParams(window.location.search).get('code') ?? '';

function judgments(setId) {
  return Object.fromEntries(Object.entries(answers[setId]).map(([k, pos]) => [k, judgmentFor(pos)]));
}

function complete(setId) {
  return Object.keys(answers[setId]).length === config.sets[setId].pairs.length;
}

async function check(setId) {
  const box = $(`res-${setId}`);
  if (!complete(setId)) {
    const left = config.sets[setId].pairs.length - Object.keys(answers[setId]).length;
    box.replaceChildren(el('p', { className: 'ed-muted', textContent: `Zostáva porovnaní: ${left}.` }));
    return;
  }
  const res = await fetch('/api/ahp/check', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ set_id: setId, judgments: judgments(setId) }),
  });
  const r = await res.json();
  results[setId] = r;
  const crit = config.sets[setId].criteria;
  const rows = Object.entries(r.weights).sort((a, b) => b[1] - a[1]).map(([k, w]) => el('div', { className: 'ahp-w' }, [
    el('span', { textContent: crit[k] }),
    el('span', { className: 'ahp-bar' }, [el('i', { style: `width:${Math.round(w * 100)}%` })]),
    el('span', { className: 'ahp-pct', textContent: `${Math.round(w * 100)} %` }),
  ]));
  document.querySelectorAll(`[data-set="${setId}"].ahp-pair`).forEach((n) => n.classList.remove('is-off'));
  let note;
  if (r.consistent) {
    note = el('p', { className: 'ahp-ok', textContent: `Odpovede sú konzistentné (CR ${formatCr(r.cr)}, limit 0,10).` });
  } else {
    const worst = worstPair(judgments(setId), r.weights);
    document.querySelector(`[data-key="${CSS.escape(worst)}"]`)?.classList.add('is-off');
    const [a, b] = worst.split('|');
    note = el('p', { className: 'ahp-bad', textContent: `Odpovede si v niečom protirečia (CR ${formatCr(r.cr)}, limit 0,10). Najviac nesedí porovnanie „${crit[a]}“ a „${crit[b]}“, je zvýraznené.` });
  }
  box.replaceChildren(el('h3', { textContent: 'Výsledné váhy' }), ...rows, note);
}

function renderSets() {
  $('ahp-sets').replaceChildren(...Object.entries(config.sets).map(([setId, s]) => {
    answers[setId] = {};
    const pairs = s.pairs.map(([a, b]) => {
      const key = `${a}|${b}`;
      const status = el('p', { className: 'ahp-say', textContent: 'Vyberte, čo je dôležitejšie.' });
      const buttons = POSITIONS.map((pos) => {
        const btn = el('button', { type: 'button', className: `ahp-dot d${Math.abs(pos)}` });
        btn.setAttribute('aria-label', positionLabel(pos, s.criteria[a], s.criteria[b], config.scale_labels));
        btn.setAttribute('aria-pressed', 'false');
        btn.addEventListener('click', () => {
          answers[setId][key] = pos;
          btn.parentElement.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === btn)));
          status.textContent = positionLabel(pos, s.criteria[a], s.criteria[b], config.scale_labels);
          check(setId);
        });
        return btn;
      });
      const row = el('div', { className: 'ahp-pair' }, [
        el('div', { className: 'ahp-scale' }, [
          el('span', { className: 'ahp-left', textContent: s.criteria[a] }),
          el('div', { className: 'ahp-dots', role: 'group' }, buttons),
          el('span', { className: 'ahp-right', textContent: s.criteria[b] }),
        ]),
        status,
      ]);
      row.dataset.set = setId;
      row.dataset.key = key;
      return row;
    });
    return el('fieldset', { className: 'ahp-set' }, [
      el('legend', { textContent: s.title }),
      ...pairs,
      el('div', { id: `res-${setId}`, className: 'ahp-result' }, [el('p', { className: 'ed-muted', textContent: `Zostáva porovnaní: ${s.pairs.length}.` })]),
    ]);
  }));
}

$('ahp-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const problems = [];
  if ($('a-name').value.trim().length < 2) problems.push('Vyplňte meno.');
  if ($('a-role').value.trim().length < 2) problems.push('Vyplňte rolu.');
  if (!$('a-code').value.trim()) problems.push('Vyplňte kód panelu, ktorý ste dostali v pozvánke.');
  for (const [setId, s] of Object.entries(config.sets)) {
    if (!complete(setId)) problems.push(`Dokončite porovnania v časti „${s.title}“.`);
    else if (!results[setId]?.consistent) problems.push(`V časti „${s.title}“ si odpovede protirečia: upravte zvýraznené porovnanie.`);
  }
  $('ahp-problems').replaceChildren(...problems.map((p) => el('li', { textContent: p })));
  $('ahp-problems').hidden = !problems.length;
  if (problems.length) return;
  $('ahp-submit').disabled = true;
  $('ahp-state').textContent = 'Odosielam…';
  try {
    for (const setId of Object.keys(config.sets)) {
      const res = await fetch('/api/ahp/responses', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ set_id: setId, judgments: judgments(setId), code: $('a-code').value.trim(),
          expert: { name: $('a-name').value.trim(), role: $('a-role').value.trim() } }),
      });
      if (res.status === 403) throw new Error('Kód panelu nesedí. Skontrolujte ho v pozvánke.');
      if (res.status === 503) throw new Error('Panel je momentálne zatvorený.');
      if (!res.ok) throw new Error('Odpovede sa nepodarilo uložiť. Skúste to znova.');
    }
    $('ahp-state').textContent = 'Ďakujeme, odpovede sú uložené. Ak ich odošlete znova, nahradia predchádzajúce.';
  } catch (err) {
    $('ahp-state').textContent = err.message;
  } finally {
    $('ahp-submit').disabled = false;
  }
});

fetch('/api/ahp/sets').then((r) => r.json()).then((c) => { config = c; renderSets(); });
