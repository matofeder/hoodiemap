import { describe, it, expect } from 'vitest';
import { getMode, getCoordsFromURL } from './main.js';

describe('getMode', () => {
  it('returns demo by default', () => {
    expect(getMode('/', '')).toBe('demo');
  });
  it('returns embed for /embed path', () => {
    expect(getMode('/embed', '?lat=48&lon=17')).toBe('embed');
  });
  it('returns view for /view/ path', () => {
    expect(getMode('/view/abc123', '')).toBe('view');
  });
  it('returns mode from query param', () => {
    expect(getMode('/', '?mode=embed')).toBe('embed');
  });
});

describe('getCoordsFromURL', () => {
  it('parses lat/lon from search params', () => {
    expect(getCoordsFromURL('?lat=48.286&lon=17.272')).toEqual({ lat: 48.286, lon: 17.272 });
  });
  it('returns null when params absent', () => {
    expect(getCoordsFromURL('')).toBeNull();
  });
  it('returns null for non-numeric lat', () => {
    expect(getCoordsFromURL('?lat=abc&lon=17')).toBeNull();
  });
});

describe('colors', () => {
  it('has entries for all POI categories', async () => {
    const { POI_COLORS } = await import('./colors.js');
    const cats = ['hospital','school','restaurant','bar','pub','grocery','pharmacy','public_office'];
    cats.forEach(cat => expect(POI_COLORS[cat]).toMatch(/^#[0-9a-fA-F]{6}$/));
  });
});
