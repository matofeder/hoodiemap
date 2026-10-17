import { describe, expect, it } from 'vitest';
import { dataFromValues, moveItem, parseNumber, validate, valuesFromData } from './form.js';

const LOC = { lat: 48.28, lon: 17.27, tier: 'address', name: null, label: 'Záhradná 12, Pezinok' };

describe('parseNumber', () => {
  it('reads Slovak-style numbers', () => {
    expect(parseNumber('189 000')).toBe(189000);
    expect(parseNumber('72,5')).toBe(72.5);
    expect(parseNumber('')).toBeNull();
    expect(parseNumber('  ')).toBeNull();
    expect(parseNumber('-1', 'int')).toBe(-1);
  });
  it('flags what is not a number', () => {
    expect(parseNumber('asi 70')).toBeNaN();
    expect(parseNumber('2,5', 'int')).toBeNaN();
  });
});

describe('form <-> data', () => {
  const values = {
    title: ' 3-izbový byt ', offer: 'sale', price_eur: '189 000', price_note: '',
    property_type: 'flat', condition: 'renovated', energy_class: '', rooms: '3', area_m2: '72', land_m2: '',
    floor: '4', floors_total: '7', year_built: '', features: ['balcony'], description: 'Svetlý byt.',
    agent_name: 'Jana Nová', agent_phone: '0900 123 456', agent_email: '', agent_agency: 'Reality Pezinok',
  };

  it('builds the API shape with nulls for empty fields', () => {
    const d = dataFromValues(values, LOC);
    expect(d).toEqual({
      location: LOC, title: '3-izbový byt', offer: 'sale', price_eur: 189000, price_note: null,
      params: {
        property_type: 'flat', condition: 'renovated', energy_class: null, features: ['balcony'],
        rooms: 3, area_m2: 72, land_m2: null, floor: 4, floors_total: 7, year_built: null,
      },
      description: 'Svetlý byt.',
      agent: { name: 'Jana Nová', phone: '0900 123 456', email: null, agency: 'Reality Pezinok' },
    });
  });

  it('shows decimals with a comma', () => {
    expect(valuesFromData({ params: { area_m2: 72.5 } }).area_m2).toBe('72,5');
  });

  it('round-trips through valuesFromData', () => {
    const d = dataFromValues(values, LOC);
    expect(dataFromValues(valuesFromData(d), LOC)).toEqual(d);
  });
});

describe('validate', () => {
  it('needs a location and real numbers', () => {
    const d = dataFromValues({ rooms: 'tri', floor: '8', floors_total: '4' }, null);
    expect(validate(d)).toEqual([
      'Najprv vyhľadajte adresu nehnuteľnosti.',
      'Počet izieb: zadajte číslo.',
      'Poschodie nemôže byť vyššie ako počet poschodí.',
    ]);
    expect(validate(dataFromValues({}, LOC))).toEqual([]);
  });
});

describe('moveItem', () => {
  it('swaps neighbours and stops at the edges', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 1)).toEqual(['b', 'a', 'c']);
    expect(moveItem(['a', 'b', 'c'], 2, -1)).toEqual(['a', 'c', 'b']);
    const list = ['a', 'b'];
    expect(moveItem(list, 0, -1)).toBe(list);
  });
});
