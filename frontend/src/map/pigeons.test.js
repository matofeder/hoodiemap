import { describe, expect, it } from 'vitest';
import { birdPosition } from './pigeons.js';

const bird = { dx: 1, dy: -1, angle: 0, dr: 0, delay: 0 };

describe('birdPosition', () => {
  it('pecks on the ground near home, then circles high, then lands back', () => {
    const ground = birdPosition([10, 10], bird, 2);
    expect(ground.flying).toBe(false);
    expect(ground.h).toBe(0);
    expect(Math.hypot(ground.x - 11, ground.y - 9)).toBeLessThan(1);
    const air = birdPosition([10, 10], bird, 13, [0, 0]);
    expect(air.flying).toBe(true);
    expect(air.h).toBeGreaterThan(10);
    expect(Math.hypot(air.x, air.y)).toBeCloseTo(11); // orbit around the given centre
    const back = birdPosition([10, 10], bird, 18);
    expect(back.h).toBeCloseTo(0);
    expect(back.x).toBeCloseTo(11 + Math.sin(0) * 0.6);
  });
});
