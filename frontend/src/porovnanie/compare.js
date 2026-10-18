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

const areaOf = (r, id) => r.index.areas.find((a) => a.id === id);

/** The indicators of one area across the addresses; a regional statistic the addresses share says so. */
function indicatorRows(areaId, results) {
  const keys = [];
  for (const r of results) {
    for (const b of areaOf(r, areaId)?.breakdown ?? []) if (!keys.some((k) => k.key === b.key)) keys.push({ key: b.key, label: b.label });
  }
  return keys.map(({ key, label }) => {
    const items = results.map((r) => areaOf(r, areaId)?.breakdown.find((b) => b.key === key));
    const values = items.map((b) => (b ? num(b.sub_score) : null));
    const facts = items.map((b) => b?.fact ?? null);
    const shared = facts.length > 1 && facts.every((f) => f != null && f === facts[0]);
    const r = row(key, label, values, { shared });
    r.cells.forEach((c, i) => { c.fact = facts[i]; });
    return r;
  });
}

/** Sections of the comparison table; each row: { id, label, status?, note?, cells: [{ value, best, fact? }] }.
 * The index first, then the index areas by group; planned areas are listed in `planned`, not as rows. */
export function buildTable(results) {
  const first = results[0].index;
  const index = row('index', 'Index HoodieMap', results.map((r) => r.index.index ?? null), {
    note: `priemer ${first.index_areas} oblastí s rovnakou váhou`,
  });
  const rows = [index];
  if (results.some((r) => r.scores.family?.weights_method === 'ahp')) {
    // A household profile adds information only once a panel set its weights; with equal weights it equals the index.
    rows.push(row('family-profile', 'Rodina', results.map((r) => r.scores.family?.score ?? null), { note: 'oblasti s váhami expertného panelu (AHP)' }));
  }
  const sections = [{ id: 'index', title: 'Index', rows }];
  for (const [gid, title] of Object.entries(first.groups)) {
    const areas = first.areas.filter((a) => a.group === gid && a.in_index).map((a) => {
      const values = results.map((r) => areaOf(r, a.id)?.score ?? null);
      const statuses = [...new Set(results.map((r) => areaOf(r, a.id)?.status).filter(Boolean))];
      return row(a.id, a.label, values, { status: statuses.join(', ') || null, indicators: indicatorRows(a.id, results) });
    });
    sections.push({ id: gid, title, rows: areas });
  }
  sections.planned = first.areas.filter((a) => !a.in_index).map((a) => a.label);
  return sections;
}

/** Where an address lies, for its column header. */
export function placeLine(region) {
  if (!region?.zuj && !region?.okres) return 'mimo Slovenska: bez štatistík území';
  return [region.zuj?.name, region.okres?.name].filter(Boolean).join(', ');
}
