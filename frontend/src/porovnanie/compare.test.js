import { describe, expect, it } from 'vitest';
import { bestOf, buildTable, parseAddresses, placeLine, serializeAddresses } from './compare.js';

const facet = (id, score, breakdown = [], status = null) => ({ id, label: `aspekt ${id}`, score, status, breakdown });
const result = (over = {}) => ({
  scores: { walk: { score: 69 }, green: { score: 45 }, quiet: { score: 100, status: 'orientačné' }, family: { score: 59, weights_method: 'equal' } },
  whoqol: {
    index: 59, min_facets: 6, facets_total: 2,
    facets: [
      facet('F16', 14, [{ key: 'crime', label: 'Kriminalita (kraj)', sub_score: 14.3, fact: 'Bratislavský kraj: 10,12' }], 'len za kraj'),
      facet('F20', 42, [{ key: 'kindergarten', label: 'Materská škola', sub_score: 80.2, fact: '526 m' }]),
    ],
  },
  ...over,
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
  const b = result({
    scores: { walk: { score: 80 }, green: { score: 45 }, quiet: { score: 70, status: 'orientačné' }, family: { score: 72, weights_method: 'equal' } },
    whoqol: { ...result().whoqol, index: 72, facets: [result().whoqol.facets[0], facet('F20', 80, [{ key: 'kindergarten', label: 'Materská škola', sub_score: 99.6, fact: '120 m' }])] },
  });
  const [whoqol, scores] = buildTable([a, b]);

  it('starts with the index, then the facets with their indicators', () => {
    expect(whoqol.rows.map((r) => r.id)).toEqual(['index', 'F16', 'F20']);
    expect(whoqol.rows[0].cells.map((c) => c.best)).toEqual([false, true]);
    const [kg] = whoqol.rows[2].indicators;
    expect(kg.cells.map((c) => [c.value, c.fact])).toEqual([[80, '526 m'], [100, '120 m']]);
  });

  it('says when a regional statistic is the same for every address', () => {
    const f16 = whoqol.rows[1];
    expect(f16.status).toBe('len za kraj');
    expect(f16.indicators[0].shared).toBe(true);
    expect(f16.cells.every((c) => !c.best)).toBe(true);
  });

  it('leaves out Rodina while its weights are equal: it would repeat the index', () => {
    expect(scores.rows.map((r) => r.id)).toEqual(['walk', 'green', 'quiet']);
    expect(scores.rows[2].status).toBe('orientačné');
    const ahp = result({ scores: { ...a.scores, family: { score: 61, weights_method: 'ahp' } } });
    expect(buildTable([ahp, b])[1].rows.map((r) => r.id)).toContain('family');
  });
});

describe('placeLine', () => {
  it('names the town and okres, or says it is outside Slovakia', () => {
    expect(placeLine({ zuj: { name: 'Pezinok' }, okres: { name: 'okres Pezinok' } })).toBe('Pezinok, okres Pezinok');
    expect(placeLine({ kraj: null, okres: null, zuj: null })).toMatch(/mimo Slovenska/);
  });
});
