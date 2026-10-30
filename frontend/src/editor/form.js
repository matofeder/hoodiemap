// Editor form <-> presentation data. Pure, so it can be unit-tested without a DOM.

const NUMBER_FIELDS = {
  rooms: 'int', area_m2: 'float', land_m2: 'float', floor: 'int', floors_total: 'int', year_built: 'int',
};

/** "72,5" -> 72.5, "189 000" -> 189000, "" -> null; NaN for anything else (caught by validate). */
export function parseNumber(raw, kind = 'float') {
  const s = String(raw ?? '').replace(/[\s  ]/g, '').replace(',', '.');
  if (!s) return null;
  if (!/^-?\d+(\.\d+)?$/.test(s)) return NaN;
  const n = Number(s);
  return kind === 'int' && !Number.isInteger(n) ? NaN : n;
}

const text = (v) => {
  const s = String(v ?? '').trim();
  return s || null;
};

/** values: flat object of form field values (strings, booleans, `features` as an array). */
export function dataFromValues(values, location) {
  const params = {
    property_type: text(values.property_type),
    condition: text(values.condition),
    energy_class: text(values.energy_class),
    features: values.features ?? [],
  };
  for (const [key, kind] of Object.entries(NUMBER_FIELDS)) params[key] = parseNumber(values[key], kind);
  return {
    location,
    title: text(values.title),
    offer: values.offer === 'rent' ? 'rent' : 'sale',
    price_eur: parseNumber(values.price_eur),
    price_note: text(values.price_note),
    params,
    description: text(values.description),
    tour_url: text(values.tour_url),
    agent: {
      name: text(values.agent_name), phone: text(values.agent_phone),
      email: text(values.agent_email), agency: text(values.agent_agency),
    },
  };
}

export function valuesFromData(d) {
  const p = d.params ?? {};
  const a = d.agent ?? {};
  const s = (v) => (v == null ? '' : typeof v === 'number' ? String(v).replace('.', ',') : String(v));
  return {
    title: s(d.title), offer: d.offer ?? 'sale', price_eur: s(d.price_eur), price_note: s(d.price_note),
    property_type: s(p.property_type), condition: s(p.condition), energy_class: s(p.energy_class),
    rooms: s(p.rooms), area_m2: s(p.area_m2), land_m2: s(p.land_m2), floor: s(p.floor),
    floors_total: s(p.floors_total), year_built: s(p.year_built), features: p.features ?? [],
    description: s(d.description), tour_url: s(d.tour_url),
    agent_name: s(a.name), agent_phone: s(a.phone), agent_email: s(a.email), agent_agency: s(a.agency),
  };
}

const FIELD_LABELS = {
  price_eur: 'Cena', rooms: 'Počet izieb', area_m2: 'Úžitková plocha', land_m2: 'Pozemok',
  floor: 'Poschodie', floors_total: 'Počet poschodí', year_built: 'Rok výstavby',
};

/** Problems in Slovak, worded for the agent; empty when the data can be saved. */
export function validate(data) {
  const problems = [];
  if (!data.location) problems.push('Najprv vyhľadajte adresu nehnuteľnosti.');
  const numbers = { price_eur: data.price_eur, ...data.params };
  for (const [key, label] of Object.entries(FIELD_LABELS)) {
    if (Number.isNaN(numbers[key])) problems.push(`${label}: zadajte číslo.`);
  }
  const { floor, floors_total: total } = data.params;
  if (Number.isFinite(floor) && Number.isFinite(total) && floor > total) {
    problems.push('Poschodie nemôže byť vyššie ako počet poschodí.');
  }
  return problems;
}

/** A copy of `list` with item i moved by delta (-1 up, +1 down); unchanged at the edges. */
export function moveItem(list, i, delta) {
  const j = i + delta;
  if (j < 0 || j >= list.length) return list;
  const out = [...list];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

/**
 * Apply an AI draft to the form values: every field the draft knows overwrites, features are added,
 * nothing is cleared. Returns the new values and the names of the fields that changed (to highlight).
 */
export function mergeDraft(values, draft) {
  const fromDraft = valuesFromData({ ...draft, agent: {} });
  const next = { ...values };
  const changed = [];
  for (const [name, value] of Object.entries(fromDraft)) {
    if (name === 'features' || name.startsWith('agent_') || value === '' || value === values[name]) continue;
    if (name === 'offer' && !draft.offer) continue;
    next[name] = value;
    changed.push(name);
  }
  const added = (draft.params?.features ?? []).filter((f) => !(values.features ?? []).includes(f));
  if (added.length) {
    next.features = [...(values.features ?? []), ...added];
    changed.push(...added.map((f) => `feature:${f}`));
  }
  return { values: next, changed };
}
