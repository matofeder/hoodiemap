import { describe, expect, it } from 'vitest';
import { formatDistance, poiTitle } from './format.js';

describe('formatDistance', () => {
  it.each([
    [0, '0 m'], [48, '50 m'], [350, '350 m'], [994, '990 m'], [995, '1,0 km'],
    [1000, '1,0 km'], [2412, '2,4 km'], [9940, '9,9 km'], [9950, '10 km'], [25000, '25 km'],
  ])('%i m -> %s', (m, s) => expect(formatDistance(m)).toBe(s));
});

describe('poiTitle', () => {
  it('uses a short name', () => expect(poiTitle({ category: 'supermarket', name: 'Lidl' })).toBe('Lidl'));
  it('falls back to label for long names', () =>
    expect(poiTitle({ category: 'hospital', name: 'Fakultná nemocnica Trnava' })).toBe('Nemocnica'));
  it('falls back to label for missing names', () => expect(poiTitle({ category: 'pharmacy', name: '' })).toBe('Lekáreň'));
  it('uses the label for transit, where a short name is just the town', () =>
    expect(poiTitle({ category: 'train', name: 'Pezinok' })).toBe('Stanica'));
  it('handles unknown categories', () => expect(poiTitle({ category: 'zoo' })).toBe('zoo'));
});
