import { describe, expect, it } from 'vitest';
import { formatDistance, formatLoadTime, poiTitle, tierLabel, warningText } from './format.js';

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
  it('always uses the city name', () =>
    expect(poiTitle({ category: 'city', name: 'Banská Bystrica' })).toBe('Banská Bystrica'));
  it('handles unknown categories', () => expect(poiTitle({ category: 'zoo' })).toBe('zoo'));
});

describe('formatLoadTime', () => {
  it.each([[12400, false, 'Načítané za 12,4 s · nové dáta'], [95, true, 'Načítané za 0,1 s · z cache'],
    [0, true, 'Načítané za 0,0 s · z cache']])('%i ms cached=%s', (ms, c, s) => expect(formatLoadTime(ms, c)).toBe(s));
  it('tier labels', () => expect(['address', 'street', 'city'].map(tierLabel)).toEqual(['adresa', 'ulica', 'mesto']));
});

describe('warningText', () => {
  it('is null when nothing on the map is missing', () => {
    expect(warningText([])).toBeNull();
    expect(warningText(undefined)).toBeNull();
    expect(warningText(['public_fallback'])).toBeNull();
  });
  it('explains missing places', () => {
    expect(warningText(['poi_fetch_failed'])).toBe('Okolité miesta (obchody, školy, zastávky…) sa nepodarilo načítať.');
  });
  it('explains a missing street highlight', () => {
    expect(warningText(['street_fetch_failed'])).toBe('Ulicu sa nepodarilo zvýrazniť.');
  });
  it('joins both', () => {
    expect(warningText(['street_fetch_failed', 'poi_fetch_failed']))
      .toBe('Okolité miesta (obchody, školy, zastávky…) sa nepodarilo načítať. Ulicu sa nepodarilo zvýrazniť.');
  });
});
