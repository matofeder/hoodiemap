import { describe, expect, it } from 'vitest';
import { detailFor } from './detail.js';

describe('detailFor', () => {
  it('address keeps everything', () => {
    expect(detailFor('address')).toMatchObject({ decor: true, people: 1, pigeons: true, property: true, streetFocus: false, shadowMap: 1024 });
  });
  it('street halves people and drops decor, shows the street', () => {
    expect(detailFor('street')).toMatchObject({ decor: false, people: 0.5, pigeons: false, property: false, streetFocus: true, shadowMap: 2048 });
  });
  it('city is the lightest', () => {
    expect(detailFor('city')).toMatchObject({ lanes: false, people: 0, seededTrees: false, maxCars: 10, property: false });
  });
  it('unknown tier behaves like address', () => expect(detailFor(undefined)).toEqual(detailFor('address')));
});
