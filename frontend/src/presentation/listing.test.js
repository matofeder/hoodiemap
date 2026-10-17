import { describe, expect, it } from 'vitest';
import scene from '../../../fixtures/pezinok-centrum.json';
import {
  featureLabels, floorLabel, formatPrice, keyFacts, localityRows, paragraphs, paramRows, roomsLabel,
} from './listing.js';

const nb = (s) => s.replace(/ | /g, ' ');

describe('formatPrice', () => {
  it('formats Slovak thousands and rent', () => {
    expect(nb(formatPrice(189000))).toBe('189 000 €');
    expect(nb(formatPrice(850, 'rent'))).toBe('850 €/mes.');
    expect(formatPrice(null)).toBe('Cena na vyžiadanie');
  });
});

describe('labels', () => {
  it('declines rooms', () => {
    expect([1, 2, 4, 5].map(roomsLabel)).toEqual(['1 izba', '2 izby', '4 izby', '5 izieb']);
  });
  it('names floors', () => {
    expect(floorLabel(4, 7)).toBe('4. poschodie z 7');
    expect(floorLabel(0)).toBe('prízemie');
    expect(floorLabel(-1)).toBe('1. podzemné podlažie');
  });
  it('builds key facts and parameter rows from what is known only', () => {
    const params = { rooms: 3, area_m2: 72, floor: 4, floors_total: 7, condition: 'renovated', energy_class: 'B' };
    expect(keyFacts(params).map(nb)).toEqual(['3 izby', '72 m²', '4. poschodie z 7', 'Po rekonštrukcii']);
    expect(nb(keyFacts({ area_m2: 72.5 })[0])).toBe('72,5 m²');
    expect(paramRows(params).map((r) => r.label)).toEqual(['Počet izieb', 'Úžitková plocha', 'Poschodie', 'Stav', 'Energetická trieda']);
    expect(paramRows({})).toEqual([]);
    expect(featureLabels(['balcony', 'nope', 'cellar'])).toEqual(['Balkón', 'Pivnica']);
  });
});

describe('localityRows', () => {
  it('lists every POI nearest first with distance and walk or drive time', () => {
    const rows = localityRows(scene);
    expect(rows.length).toBe(scene.near_pois.length + scene.far_pois.length);
    const billa = rows.find((r) => r.name === 'Billa');
    expect(billa).toMatchObject({ label: 'Supermarket', distance: '70 m', time: '2 min pešo' });
    const ba = rows.find((r) => r.label === 'Bratislava');
    expect(ba).toMatchObject({ name: 'mesto', distance: '20 km' });
    expect(ba.time).toMatch(/min autom$/);
    expect(rows.at(-1).label).toBe('Trnava');
  });
  it('drops a name that only repeats the category label', () => {
    const rows = localityRows({ near_pois: [{ category: 'playground', name: 'Ihrisko', distance_m: 40 }], far_pois: [] });
    expect(rows[0].name).toBeNull();
  });
  it('copes with a scene without POIs', () => {
    expect(localityRows({})).toEqual([]);
  });
});

describe('paragraphs', () => {
  it('splits on blank lines', () => {
    expect(paragraphs('Prvý.\nstále prvý\n\n  Druhý.  \n\n\n')).toEqual(['Prvý.\nstále prvý', 'Druhý.']);
    expect(paragraphs(null)).toEqual([]);
  });
});
