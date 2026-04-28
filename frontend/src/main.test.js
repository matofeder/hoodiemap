import { describe, it, expect } from 'vitest';

describe('getMode', () => {
  it('returns correct mode for paths and params', () => {
    function getMode(pathname, search) {
      const params = new URLSearchParams(search);
      if (pathname.startsWith('/embed')) return 'embed';
      if (pathname.startsWith('/view/')) return 'view';
      return params.get('mode') || 'demo';
    }
    expect(getMode('/', '')).toBe('demo');
    expect(getMode('/embed', '?lat=48&lon=17')).toBe('embed');
    expect(getMode('/view/abc123', '')).toBe('view');
    expect(getMode('/', '?mode=embed')).toBe('embed');
  });
});

describe('getCoordsFromURL', () => {
  it('parses lat/lon from search params', () => {
    function getCoordsFromURL(search) {
      const params = new URLSearchParams(search);
      const lat = parseFloat(params.get('lat'));
      const lon = parseFloat(params.get('lon'));
      if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
      return null;
    }
    expect(getCoordsFromURL('?lat=48.286&lon=17.272')).toEqual({ lat: 48.286, lon: 17.272 });
    expect(getCoordsFromURL('')).toBeNull();
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
