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
