import { describe, expect, it } from 'vitest';
import { areaDetail, breakdownTable, emptyFacts, factLine, missingLine, visibleScores } from './facts.js';

const nb = (s) => s.replace(/ | /g, ' ');

describe('factLine', () => {
  it('describes a nearby place', () => {
    const f = factLine({ label: 'Potraviny', name: 'Billa', distance_m: 71, minutes: 2, count_1km: 7 });
    expect(nb(f.detail)).toBe('Billa · 70 m · 2 min pešo · 7 do 1 km');
  });
  it('hides a name that repeats the label and a count of one', () => {
    expect(nb(factLine({ label: 'Materská škola', name: 'Materská škola', distance_m: 281, minutes: 5, count_1km: 1 }).detail))
      .toBe('280 m · 5 min pešo');
  });
  it('handles green, presence and penalties', () => {
    expect(nb(factLine({ label: 'Zeleň do 300 m', share: 0.05, target: 0.3 }).detail)).toBe('5 % plochy · odporúčanie 30 %');
    expect(factLine({ label: 'Les', present: false }).detail).toBe('nie');
    expect(nb(factLine({ label: 'Park', name: 'Zámocký Park', distance_m: 467, area_ha: 7.1 }).detail))
      .toBe('Zámocký Park · 470 m · 7,1 ha');
    expect(nb(factLine({ label: 'Cesta II. triedy', distance_m: 80, penalty: 8 }).detail)).toBe('80 m · −8 b.');
    expect(factLine({ label: 'Bary', count: 1, penalty: 5 }).detail).toBe('1 podnik · −5 b.');
    expect(factLine({ label: 'Verejná zeleň', name: null, distance_m: null }).detail).toBe('nenašli sme');
  });
});

describe('missing and empty', () => {
  it('words what was not found', () => {
    expect(missingLine('walk', ['Potraviny'])).toBe('Do 2,5 km sme nenašli: potraviny.');
    expect(missingLine('family', ['Bezpečnosť'])).toBe('Chýbajú dáta pre oblasti: Bezpečnosť.');
    expect(missingLine('walk', [])).toBeNull();
    expect(emptyFacts('quiet')).toMatch(/nenašli/);
    expect(emptyFacts('walk')).toBeNull();
  });
});

describe('breakdownTable', () => {
  it('shows sub-score × weight = points and the weights note', () => {
    const t = breakdownTable({ score: 17, weights_method: 'equal', breakdown: [
      { label: 'Materská škola', fact: '100 m', sub_score: 100, weight: 0.1667, points: 16.7 },
      { label: 'Lekár', fact: 'nenájdené', sub_score: 0, weight: 0.1667, points: 0 },
    ] });
    expect(t.rows[0]).toEqual({ label: 'Materská škola', fact: '100 m', sub: '100,0', weight: '16,7 %', points: '16,7' });
    expect(t.total).toBe('17');
    expect(t.note).toMatch(/rovnaké/);
  });
  it('lists deductions for the quiet score', () => {
    const t = breakdownTable({ score: 70, weights_method: 'penalties', breakdown: [{ label: 'Cesta I. triedy', fact: '40 m', points: -30 }] });
    expect(t.start).toBe('Začiatok: 100 bodov');
    expect(t.rows[0].points).toBe('-30');
  });
});

describe('areas and tiles', () => {
  it('shows Rodina only with panel weights', () => {
    const keys = (fam) => visibleScores({ walk: {}, green: {}, quiet: {}, family: fam }).map((x) => x.key);
    expect(keys({ weights_method: 'equal' })).toEqual(['walk', 'green', 'quiet']);
    expect(keys({ weights_method: 'ahp' })).toEqual(['walk', 'green', 'quiet', 'family']);
  });
  it('lists indicators, regional facts without the source, and planned areas', () => {
    expect(areaDetail({ in_index: true, score: 58, breakdown: [
      { key: 'wage', label: 'Priemerná mzda (okres)', sub_score: 39.7, fact: 'okres Pezinok: 1579 € (2025); ŠÚ SR' },
      { key: 'doctors', label: 'Lekár', sub_score: 16.9, fact: '1269 m' }] }))
      .toBe('Priemerná mzda (okres) 40 (okres Pezinok: 1579 € (2025)) · Lekár 17');
    expect(areaDetail({ in_index: false, planned: 'PM2,5 (SHMÚ)', norm: 'WHO 2021' })).toBe('Pripravujeme: PM2,5 (SHMÚ). Norma: WHO 2021.');
    expect(areaDetail({ in_index: true, score: null })).toMatch(/len pre Slovensko/);
  });
});
