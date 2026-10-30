import { describe, expect, it } from 'vitest';
import { listingUrl, pickVariant, priceLabel, readTags } from './funnel.js';

describe('pickVariant', () => {
  const v = ['9', '19'];
  it('honours a forced, then a stored variant', () => {
    expect(pickVariant(v, { forced: '19', stored: '9' })).toBe('19');
    expect(pickVariant(v, { forced: '99', stored: '9' })).toBe('9');
  });
  it('splits new visitors at random', () => {
    expect(pickVariant(v, { random: () => 0.1 })).toBe('9');
    expect(pickVariant(v, { random: () => 0.9 })).toBe('19');
    expect(pickVariant(v, { random: () => 0.999999 })).toBe('19');
    expect(pickVariant([], {})).toBeNull();
  });
});

describe('readTags', () => {
  it('reads utm tags and keeps the session ones', () => {
    expect(readTags('?utm_source=fb&utm_campaign=jesen-2026')).toEqual({ source: 'fb', campaign: 'jesen-2026' });
    expect(readTags('', { source: 'google', campaign: null })).toEqual({ source: 'google', campaign: null });
  });
  it('drops anything that is not a plain tag', () => {
    expect(readTags('?utm_source=%3Cscript%3E&utm_campaign=a%20b')).toEqual({ source: null, campaign: null });
  });
});

describe('labels', () => {
  it('shows the price and checks listing links', () => {
    expect(priceLabel('19')).toBe('Správa za 19 €');
    expect(listingUrl(' https://www.nehnutelnosti.sk/detail/x ')).toBe('https://www.nehnutelnosti.sk/detail/x');
    expect(listingUrl('Záhradná 12')).toBeNull();
  });
});
