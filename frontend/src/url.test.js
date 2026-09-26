import { describe, expect, it } from 'vitest';
import { getCoordsFromURL, getViewFromURL, isFixture, sceneUrl, viewToSearch } from './url.js';

describe('url', () => {
  it('parses coords', () => expect(getCoordsFromURL('?lat=48.1&lon=17.2')).toEqual({ lat: 48.1, lon: 17.2 }));
  it('returns null when missing', () => expect(getCoordsFromURL('?lat=48.1')).toBeNull());
  it('rejects out-of-range', () => expect(getCoordsFromURL('?lat=100&lon=17')).toBeNull());
  it('detects fixture', () => {
    expect(isFixture('?fixture=true')).toBe(true);
    expect(isFixture('')).toBe(false);
  });
});

describe('view URL', () => {
  it('reads tier, name and label', () => {
    expect(getViewFromURL('?lat=48.1&lon=17.1&tier=street&name=Z%C3%A1hradn%C3%A1&label=Z%C3%A1hradn%C3%A1%2C+Pezinok'))
      .toEqual({ lat: 48.1, lon: 17.1, tier: 'street', name: 'Záhradná', label: 'Záhradná, Pezinok' });
  });
  it('plain lat/lon is the address tier; bad tier falls back', () => {
    expect(getViewFromURL('?lat=48.1&lon=17.1')).toEqual({ lat: 48.1, lon: 17.1, tier: 'address', name: null, label: null });
    expect(getViewFromURL('?lat=48.1&lon=17.1&tier=planet').tier).toBe('address');
    expect(getViewFromURL('?tier=city')).toBeNull();
  });
  it('round-trips and builds the scene URL', () => {
    const v = { lat: 48.1, lon: 17.1, tier: 'street', name: 'Nám. SNP', label: 'Nám. SNP, Pezinok' };
    expect(getViewFromURL(viewToSearch(v))).toEqual(v);
    expect(sceneUrl(v, false)).toBe('/api/scene?lat=48.1&lon=17.1&tier=street&name=N%C3%A1m.+SNP');
    expect(sceneUrl({ ...v, tier: 'city', name: 'Pezinok' }, true)).toBe('/api/scene?lat=48.1&lon=17.1&tier=city&fixture=true');
  });
});
