import { describe, it, expect } from 'vitest';
import { _formatDistance, _bearingToCardinal, _resolveCollisions } from './frame.js';

describe('_formatDistance', () => {
  it('returns meters for < 1000', () => {
    expect(_formatDistance(850)).toBe('850 m');
  });
  it('rounds meters', () => {
    expect(_formatDistance(423)).toBe('423 m');
  });
  it('returns km with 1 decimal for >= 1000', () => {
    expect(_formatDistance(2100)).toBe('2.1 km');
  });
  it('returns km for exactly 1000', () => {
    expect(_formatDistance(1000)).toBe('1.0 km');
  });
});

describe('_bearingToCardinal', () => {
  it('0° is S (Sever = North)', () => {
    expect(_bearingToCardinal(0)).toBe('S');
  });
  it('90° is V (Východ = East)', () => {
    expect(_bearingToCardinal(90)).toBe('V');
  });
  it('180° is J (Juh = South)', () => {
    expect(_bearingToCardinal(180)).toBe('J');
  });
  it('270° is Z (Západ = West)', () => {
    expect(_bearingToCardinal(270)).toBe('Z');
  });
  it('315° is SZ (Severozápad = NW)', () => {
    expect(_bearingToCardinal(315)).toBe('SZ');
  });
  it('360° wraps to S', () => {
    expect(_bearingToCardinal(360)).toBe('S');
  });
  it('handles negative bearings (-45° → SZ)', () => {
    expect(_bearingToCardinal(-45)).toBe('SZ');
  });
});

describe('_resolveCollisions', () => {
  it('leaves non-colliding POIs unchanged', () => {
    const pois = [
      { bearing_deg: 10 },
      { bearing_deg: 90 },
      { bearing_deg: 200 },
    ];
    const result = _resolveCollisions(pois);
    expect(result[0].bearing_deg).toBe(10);
    expect(result[1].bearing_deg).toBe(90);
    expect(result[2].bearing_deg).toBe(200);
  });

  it('separates two POIs closer than 15°', () => {
    const pois = [
      { bearing_deg: 45 },
      { bearing_deg: 50 },
    ];
    const result = _resolveCollisions(pois);
    const diff = Math.abs(result[1].bearing_deg - result[0].bearing_deg);
    expect(diff).toBeGreaterThanOrEqual(15);
  });

  it('does not mutate input objects', () => {
    const pois = [{ bearing_deg: 45 }, { bearing_deg: 50 }];
    _resolveCollisions(pois);
    expect(pois[0].bearing_deg).toBe(45);
    expect(pois[1].bearing_deg).toBe(50);
  });

  it('separates three collinear POIs', () => {
    const pois = [{ bearing_deg: 45 }, { bearing_deg: 45 }, { bearing_deg: 45 }];
    const result = _resolveCollisions(pois);
    expect(Math.abs(result[1].bearing_deg - result[0].bearing_deg)).toBeGreaterThanOrEqual(15);
    expect(Math.abs(result[2].bearing_deg - result[1].bearing_deg)).toBeGreaterThanOrEqual(15);
    expect(Math.abs(result[2].bearing_deg - result[0].bearing_deg)).toBeGreaterThanOrEqual(15);
  });

  it('handles wraparound bearings (350° and 5°)', () => {
    const pois = [{ bearing_deg: 350 }, { bearing_deg: 5 }];
    const result = _resolveCollisions(pois);
    let diff = result[1].bearing_deg - result[0].bearing_deg;
    if (diff > 180) diff -= 360;
    if (diff < -180) diff += 360;
    expect(Math.abs(diff)).toBeGreaterThanOrEqual(15);
  });
});
