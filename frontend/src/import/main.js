import '../editor/editor.css';

const $ = (id) => document.getElementById(id);
const ERRORS = {
  403: 'Admin token nesedí.',
  422: 'Toto nie je odkaz na jeden inzerát z nehnutelnosti.sk, alebo sa z neho nedali prečítať údaje.',
  502: 'Inzerát alebo mapové dáta sa teraz nepodarilo načítať. Skúste to o chvíľu.',
  503: 'Import je na serveri vypnutý (chýba HOODIEMAP_ADMIN_TOKEN).',
};

function readStore(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function writeStore(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
}

$('i-token').value = readStore('hm.admin', '');

$('import-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = $('i-url').value.trim();
  if (!url) return void ($('import-state').textContent = 'Vložte odkaz na inzerát.');
  writeStore('hm.admin', $('i-token').value);
  $('import-go').disabled = true;
  $('import-result').hidden = true;
  $('import-state').textContent = 'Načítavam inzerát, mapu okolia a fotky… Zvyčajne to trvá 10 až 30 sekúnd.';
  try {
    const res = await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Token': $('i-token').value },
      body: JSON.stringify({
        url, demo_for: $('i-for').value.trim() || null,
        expires_in_days: Number.parseInt($('i-days').value, 10) || 30,
        fixture: new URLSearchParams(window.location.search).get('fixture') === 'true',
      }),
    });
    if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
    show(await res.json());
    $('import-state').textContent = '';
  } catch (err) {
    $('import-state').textContent = ERRORS[err.status] ?? 'Import zlyhal. Skúste to znova.';
  } finally {
    $('import-go').disabled = false;
  }
});

function show(r) {
  const edit = `/upravit/${encodeURIComponent(r.id)}#${r.edit_token}`;
  $('r-title').textContent = r.title || r.label || 'Ukážka';
  $('r-meta').textContent = [r.label, r.demo_for ? `ukážka pre ${r.demo_for}` : null, `${r.photos} fotiek`].filter(Boolean).join(' · ');
  $('r-warnings').replaceChildren(...r.warnings.map((w) => Object.assign(document.createElement('li'), { textContent: w })));
  $('r-warnings').hidden = !r.warnings.length;
  $('r-edit').href = edit;
  $('r-open').href = `/p/${encodeURIComponent(r.id)}`;
  $('import-result').hidden = false;
  const recent = readStore('hm.recent', []).filter((x) => x.id !== r.id);
  writeStore('hm.recent', [{ id: r.id, token: r.edit_token, title: r.title, label: r.label, at: Date.now() }, ...recent].slice(0, 12));
}
