import { describe, expect, it } from 'vitest';
import { getCoordsFromURL, isFixture } from './url.js';

describe('url', () => {
  it('parses coords', () => expect(getCoordsFromURL('?lat=48.1&lon=17.2')).toEqual({ lat: 48.1, lon: 17.2 }));
  it('returns null when missing', () => expect(getCoordsFromURL('?lat=48.1')).toBeNull());
  it('rejects out-of-range', () => expect(getCoordsFromURL('?lat=100&lon=17')).toBeNull());
  it('detects fixture', () => {
    expect(isFixture('?fixture=true')).toBe(true);
    expect(isFixture('')).toBe(false);
  });
});
