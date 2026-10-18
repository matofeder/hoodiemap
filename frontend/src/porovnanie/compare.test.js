import { describe, expect, it } from 'vitest';
import { bestOf, buildTable, parseAddresses, placeLine, serializeAddresses } from './compare.js';

const area = (id, group, score, breakdown = [], status = null, inIndex = true) => ({ id, label: `oblasť ${id}`, group, score, status, breakdown, in_index: inIndex });
const result = ({ index = 59, family = 50, fam = { score: 59, weights_method: 'equal' }, safety = 14 } = {}) => ({
  scores: { family: fam },
  index: {
    index, index_areas: 3, groups: { okolie: 'Okolie adresy', uzemie: 'Územie (štatistiky)' },
    areas: [
      area('walk', 'okolie', 69),
      area('family', 'okolie', family, [{ key: 'kindergarten', label: 'Materská škola', sub_score: family, fact: `${family} m` }]),
      area('air', 'okolie', null, [], 'pripravujeme', false),
      area('safety', 'uzemie', safety, [{ key: 'crime', label: 'Kriminalita (kraj)', sub_score: 14.3, fact: 'Bratislavský kraj: 10,12' }], 'len za kraj'),
    ],
  },
});

describe('addresses in the URL', () => {
  it('round-trips, keeping commas in the label', () => {
    const list = [{ lat: 48.28646, lon: 17.27221, label: 'Záhradná, Pezinok' }, { lat: 48.1, lon: 17.1, label: 'SNP' }];
    expect(parseAddresses(serializeAddresses(list, true))).toEqual(list);
    expect(serializeAddresses(list, true)).toContain('fixture=true');
  });

  it('drops invalid points and keeps at most five', () => {
    const q = ['a=x,1,A', 'a=95,1,B', ...Array.from({ length: 7 }, (_, i) => `a=48,${17 + i},P${i}`)].join('&');
    const got = parseAddresses(`?${q}`);
    expect(got.map((p) => p.label)).toEqual(['P0', 'P1', 'P2', 'P3', 'P4']);
  });
});

describe('bestOf', () => {
  it('marks the top value, ties included', () => expect(bestOf([3, 7, 7, null])).toEqual([1, 2]));
  it('marks nothing when all equal or only one value', () => {
    expect(bestOf([5, 5])).toEqual([]);
    expect(bestOf([5, null])).toEqual([]);
  });
});

describe('buildTable', () => {
  const a = result();
  const b = result({ index: 72, family: 80 });
  const sections = buildTable([a, b]);
  const [idx, okolie, uzemie] = sections;

  it('starts with the index, then the index areas by group', () => {
    expect(sections.map((x) => x.title)).toEqual(['Index', 'Okolie adresy', 'Územie (štatistiky)']);
    expect(idx.rows.map((r) => r.id)).toEqual(['index']);
    expect(idx.rows[0].cells.map((c) => c.best)).toEqual([false, true]);
    expect(okolie.rows.map((r) => r.id)).toEqual(['walk', 'family']);
    const [kg] = okolie.rows[1].indicators;
    expect(kg.cells.map((c) => [c.value, c.fact])).toEqual([[50, '50 m'], [80, '80 m']]);
  });

  it('lists planned areas apart, not as rows', () => {
    expect(sections.planned).toEqual(['oblasť air']);
  });

  it('says when a regional statistic is the same for every address', () => {
    const safety = uzemie.rows[0];
    expect(safety.status).toBe('len za kraj');
    expect(safety.indicators[0].shared).toBe(true);
    expect(safety.cells.every((c) => !c.best)).toBe(true);
  });

  it('adds Rodina only once a panel set its weights: with equal weights it repeats the index', () => {
    const ahp = result({ fam: { score: 61, weights_method: 'ahp' } });
    expect(buildTable([ahp, b])[0].rows.map((r) => r.id)).toEqual(['index', 'family-profile']);
  });
});

describe('placeLine', () => {
  it('names the town and okres, or says it is outside Slovakia', () => {
    expect(placeLine({ zuj: { name: 'Pezinok' }, okres: { name: 'okres Pezinok' } })).toBe('Pezinok, okres Pezinok');
    expect(placeLine({ kraj: null, okres: null, zuj: null })).toMatch(/mimo Slovenska/);
  });
});
