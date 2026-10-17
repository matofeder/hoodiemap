import '../editor/editor.css';

const $ = (id) => document.getElementById(id);
const pct = (a, b) => (b ? `${Math.round((a / b) * 100)} %` : '–');
const cell = (text) => Object.assign(document.createElement('td'), { textContent: String(text) });

try { $('a-token').value = JSON.parse(localStorage.getItem('hm.admin')) ?? ''; } catch { /* none saved */ }

function headers() {
  return { 'X-Admin-Token': $('a-token').value };
}

$('admin-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  try { localStorage.setItem('hm.admin', JSON.stringify($('a-token').value)); } catch { /* private mode */ }
  $('a-state').textContent = 'Načítavam…';
  try {
    const res = await fetch('/api/landing/stats', { headers: headers() });
    if (res.status === 403) throw new Error('Admin token nesedí.');
    if (!res.ok) throw new Error('Štatistiky sa nepodarilo načítať.');
    render(await res.json());
    $('a-state').textContent = '';
  } catch (err) {
    $('a-state').textContent = err.message;
  }
});

function render({ rows, totals }) {
  $('a-totals').replaceChildren(...[
    ['Videli', totals.views], ['Klikli', totals.cta], ['Nechali e-mail', totals.signups],
    ['Klik / videli', pct(totals.cta, totals.views)], ['E-mail / klikli', pct(totals.signups, totals.cta)],
  ].map(([label, value]) => {
    const box = document.createElement('div');
    box.className = 'ed-stat';
    box.append(Object.assign(document.createElement('strong'), { textContent: String(value) }),
      Object.assign(document.createElement('span'), { textContent: label }));
    return box;
  }));
  $('a-rows').replaceChildren(...rows.map((r) => {
    const tr = document.createElement('tr');
    tr.append(cell(`${r.variant} €`), cell(r.source ?? 'priamo'), cell(r.views), cell(r.cta), cell(r.signups),
      cell(pct(r.cta, r.views)), cell(pct(r.signups, r.cta)), cell(r.soon), cell(r.with_listing));
    return tr;
  }));
  $('a-result').hidden = false;
}

$('a-csv').addEventListener('click', async () => {
  const res = await fetch('/api/landing/export.csv', { headers: headers() });
  if (!res.ok) return void ($('a-state').textContent = 'Export sa nepodaril.');
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: 'prever-waitlist.csv' });
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});
