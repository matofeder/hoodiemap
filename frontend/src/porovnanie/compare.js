/** Porovnanie adries: the addresses live in the URL (?a=lat,lon,label&a=…), the table is built from
 * /api/score results without any new arithmetic: every number shown is one the score page explains. */

export const MAX_ADDRESSES = 5;

const num = (v) => Math.round(v);

/** ?a=48.28646,17.27221,Záhradná, Pezinok -> [{ lat, lon, label }]; the label may contain commas. */
export function parseAddresses(search) {
  const out = [];
  for (const a of new URLSearchParams(search).getAll('a')) {
    const [lat, lon, ...rest] = a.split(',');
    const point = { lat: Number(lat), lon: Number(lon), label: rest.join(',').trim() || 'Adresa' };
    if (Number.isFinite(point.lat) && Number.isFinite(point.lon) && Math.abs(point.lat) <= 90 && Math.abs(point.lon) <= 180) {
      out.push(point);
    }
  }
  return out.slice(0, MAX_ADDRESSES);
}

export function serializeAddresses(list, fixture = false) {
  const p = new URLSearchParams();
  for (const { lat, lon, label } of list) p.append('a', `${lat},${lon},${label}`);
  if (fixture) p.set('fixture', 'true');
  return `?${p}`;
}

/** Which columns hold the row's best value: none when fewer than two values or all equal. */
export function bestOf(values) {
  const have = values.filter((v) => v != null);
  if (have.length < 2) return [];
  const top = Math.max(...have);
  if (have.every((v) => v === top)) return [];
  return values.flatMap((v, i) => (v === top ? [i] : []));
}

function row(id, label, values, extra = {}) {
  const best = bestOf(values);
  return { id, label, cells: values.map((value, i) => ({ value, best: best.includes(i) })), ...extra };
}

/** The indicators of one facet across the addresses; a regional statistic the addresses share says so. */
function indicatorRows(facetId, results) {
  const keys = [];
  for (const r of results) {
    const facet = r.whoqol.facets.find((f) => f.id === facetId);
    for (const b of facet?.breakdown ?? []) if (!keys.some((k) => k.key === b.key)) keys.push({ key: b.key, label: b.label });
  }
  return keys.map(({ key, label }) => {
    const items = results.map((r) => r.whoqol.facets.find((f) => f.id === facetId)?.breakdown.find((b) => b.key === key));
    const values = items.map((b) => (b ? num(b.sub_score) : null));
    const facts = items.map((b) => b?.fact ?? null);
    const shared = facts.length > 1 && facts.every((f) => f != null && f === facts[0]);
    const r = row(key, label, values, { shared });
    r.cells.forEach((c, i) => { c.fact = facts[i]; });
    return r;
  });
}

/** Sections of the comparison table; each row: { id, label, status?, note?, cells: [{ value, best, fact? }] }. */
export function buildTable(results) {
  const first = results[0];
  const facets = first.whoqol.facets.map((f) => {
    const values = results.map((r) => r.whoqol.facets.find((x) => x.id === f.id)?.score ?? null);
    const statuses = [...new Set(results.map((r) => r.whoqol.facets.find((x) => x.id === f.id)?.status).filter(Boolean))];
    return row(f.id, `${f.id} ${f.label}`, values, { status: statuses.join(', ') || null, indicators: indicatorRows(f.id, results) });
  });
  const index = row('index', 'Index prostredia', results.map((r) => r.whoqol.index ?? null), {
    note: `priemer aspektov s dátami, aspoň ${first.whoqol.min_facets} z ${first.whoqol.facets_total}`,
  });
  const scores = [
    ['walk', 'Pešo', 'Walk Score: služby podľa vzdialenosti chôdzou'],
    ['green', 'Zeleň', 'WHO 0,5 ha do 300 m, podiel zelene, 20 ha do 2 km'],
    ['quiet', 'Pokoj', 'cesty, železnica a bary v okolí'],
  ].map(([key, label, note]) => row(key, label, results.map((r) => r.scores[key]?.score ?? null), {
    note, status: results.map((r) => r.scores[key]?.status).find(Boolean) ?? null,
  }));
  const sections = [
    { id: 'whoqol', title: 'Prostredie podľa WHOQOL-BREF', rows: [index, ...facets] },
    { id: 'scores', title: 'Samostatné skóre', rows: scores },
  ];
  // A household profile adds information only once a panel set its weights; with equal weights it equals the index.
  if (results.some((r) => r.scores.family?.weights_method === 'ahp')) {
    scores.push(row('family', 'Rodina', results.map((r) => r.scores.family?.score ?? null), { note: 'aspekty WHOQOL s váhami expertného panelu (AHP)' }));
  }
  return sections;
}

/** Where an address lies, for its column header. */
export function placeLine(region) {
  if (!region?.zuj && !region?.okres) return 'mimo Slovenska: bez štatistík území';
  return [region.zuj?.name, region.okres?.name].filter(Boolean).join(', ');
}
