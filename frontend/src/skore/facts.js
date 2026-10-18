import { formatDistance } from '../format.js';

export const SCORES = [
  { key: 'walk', label: 'Pešo', question: 'Čo vybavíte bez auta' },
  { key: 'green', label: 'Zeleň', question: 'Park, les a zeleň okolo' },
  { key: 'family', label: 'Rodina', question: 'Škôlka, škola, ihrisko, lekár' },
  { key: 'quiet', label: 'Pokoj', question: 'Hlavné cesty, železnica, bary' },
];

const ha = (v) => `${String(v).replace('.', ',')} ha`;
const pct = (v) => `${Math.round(v * 100)} %`;

/** One line of "why" under a score: { title, detail } in Slovak. */
export function factLine(fact) {
  const name = fact.name && fact.name !== fact.label ? fact.name : null;
  if ('share' in fact) {
    return { title: fact.label, detail: `${pct(fact.share)} plochy · odporúčanie ${pct(fact.target)}` };
  }
  if ('present' in fact) {
    return { title: fact.label, detail: fact.present ? (name ? `áno · ${name}` : 'áno') : 'nie' };
  }
  if ('penalty' in fact) {
    const where = fact.count != null ? `${fact.count} ${fact.count === 1 ? 'podnik' : fact.count < 5 ? 'podniky' : 'podnikov'}`
      : formatDistance(fact.distance_m);
    return { title: fact.label, detail: `${where} · −${fact.penalty} b.` };
  }
  if (fact.distance_m == null) return { title: fact.label, detail: 'nenašli sme' };
  const parts = [name, formatDistance(fact.distance_m)];
  if (fact.minutes != null) parts.push(`${fact.minutes} min pešo`);
  if (fact.area_ha != null) parts.push(ha(fact.area_ha));
  if (fact.count_1km != null && fact.count_1km > 1) parts.push(`${fact.count_1km} do 1 km`);
  return { title: fact.label, detail: parts.filter(Boolean).join(' · ') };
}

export function missingLine(kind, missing) {
  if (!missing?.length) return null;
  if (kind === 'green') return `Nenašli sme ${missing.join(', ')}.`;
  return `Do 2,5 km sme nenašli: ${missing.join(', ').toLowerCase()}.`;
}

/** The quiet score lists only what lowers it; an empty list deserves a sentence. */
export function emptyFacts(kind) {
  return kind === 'quiet' ? 'V okolí sme nenašli hlavnú cestu, železnicu ani bary, ktoré by znižovali pokoj.' : null;
}

const num = (v, digits = 1) => v.toFixed(digits).replace('.', ',');

export const WEIGHTS_NOTE = {
  walkscore: 'Váhy kategórií: Walk Score (Brewster a kol. 2009).',
  equal: 'Váhy: rovnaké pre všetky ukazovatele (OECD/JRC 2008), kým neodpovie expertný panel (AHP).',
  ahp: 'Váhy: expertný panel metódou AHP.',
  penalties: 'Od 100 bodov odpočítavame zrážky. Orientačný odhad, nie hlukový model.',
};

/** The step-by-step table under a score: display rows plus the total line, all as strings. */
export function breakdownTable(s) {
  if (s.weights_method === 'penalties') {
    const rows = s.breakdown.map((r) => ({ label: r.label, fact: r.fact, sub: '', weight: '', points: `${r.points}` }));
    return { head: ['Zdroj', 'Vzdialenosť', '', '', 'Body'], start: 'Začiatok: 100 bodov', rows,
      total: `${s.score}`, note: WEIGHTS_NOTE.penalties };
  }
  const rows = s.breakdown.map((r) => ({
    label: r.label, fact: r.fact, sub: num(r.sub_score), weight: `${num(r.weight * 100)} %`, points: num(r.points),
  }));
  return { head: ['Ukazovateľ', 'Fakt', 'Čiastkové skóre', 'Váha', 'Body'], start: null, rows,
    total: `${s.score}`, note: WEIGHTS_NOTE[s.weights_method] ?? '' };
}
