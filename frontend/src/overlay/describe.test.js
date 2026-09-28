import { describe, expect, it } from 'vitest';
import { buildingInfo, floorsLabel, openingHours, poiInfo, travelTime } from './describe.js';

describe('travelTime', () => {
  it('walking for nearby places (with a detour factor)', () => {
    expect(travelTime(70)).toBe('≈ 2 min pešo');
    expect(travelTime(0)).toBe('≈ 1 min pešo');
    expect(travelTime(2000)).toBe('≈ 33 min pešo');
  });
  it('driving beyond 2.5 km', () => {
    expect(travelTime(5800)).toBe('≈ 9 min autom');
    expect(travelTime(20000)).toBe('≈ 30 min autom');
  });
});

describe('openingHours', () => {
  it('translates OSM day codes to Slovak', () =>
    expect(openingHours('Mo-Fr 08:00-18:00; Sa 08:00-12:00; Su off')).toBe('Po-Pi 08:00-18:00; So 08:00-12:00; Ne zatvorené'));
  it('handles 24/7 and holidays', () => {
    expect(openingHours('24/7')).toBe('nonstop');
    expect(openingHours('Mo-Su 07:00-22:00; PH off')).toBe('Po-Ne 07:00-22:00; sviatky zatvorené');
  });
  it('missing -> null', () => expect(openingHours(undefined)).toBeNull());
});

describe('floorsLabel', () => {
  it.each([[1, '1 podlažie'], [2, '2 podlažia'], [4, '4 podlažia'], [5, '5 podlaží'], [12, '12 podlaží']])(
    '%s -> %s', (n, s) => expect(floorsLabel(n)).toBe(s));
});

describe('poiInfo', () => {
  it('name as title, category + distance + time, opening hours', () => {
    const info = poiInfo({ category: 'pharmacy', name: 'Lekáreň FARMÁCIA', distance_m: 91, opening_hours: 'Mo-Fr 08:00-18:00' });
    expect(info).toEqual({
      title: 'Lekáreň FARMÁCIA',
      color: '#3AAFA9',
      lines: ['Lekáreň · 90 m · ≈ 2 min pešo', 'Otvorené: Po-Pi 08:00-18:00'],
    });
  });
  it('puts each opening-hours rule on its own line', () =>
    expect(poiInfo({ category: 'supermarket', name: 'Billa', distance_m: 69, opening_hours: 'Mo-Sa 07:00-20:00; Su 08:00-18:00' }).lines)
      .toEqual(['Supermarket · 70 m · ≈ 2 min pešo', 'Otvorené: Po-So 07:00-20:00', 'Ne 08:00-18:00']));
  it('falls back to the category label, cities get no category line', () => {
    expect(poiInfo({ category: 'bank', name: '', distance_m: 103 }).title).toBe('Banka');
    expect(poiInfo({ category: 'city', name: 'Trnava', distance_m: 24825 }).lines).toEqual(['25 km · ≈ 37 min autom']);
  });
  it('landmarks use their kind as the label', () =>
    expect(poiInfo({ category: 'landmark', kind: 'Radnica', name: 'Stará radnica', distance_m: 40 }).lines[0])
      .toBe('Radnica · 40 m · ≈ 1 min pešo'));
});

describe('buildingInfo', () => {
  it('without OSM facts: only the kind, no guessed floors', () =>
    expect(buildingInfo({ kind: 'apartment', height: 12 })).toEqual({ title: 'Bytový dom', lines: [] }));
  it('marks the property', () =>
    expect(buildingInfo({ kind: 'house', height: 6 }, { isProperty: true }).title).toBe('Na predaj · Rodinný dom'));
  it('a POI building shows the POI', () =>
    expect(buildingInfo({ kind: 'commercial', height: 8 }, { poi: { category: 'supermarket', name: 'Billa', distance_m: 69 } }).title)
      .toBe('Billa'));
  it('name, address, facts and distance from the property', () =>
    expect(buildingInfo(
      { kind: 'civic', height: 30, name: 'Dóm sv. Alžbety', type: 'place_of_worship', address: 'Hlavná 1',
        levels: 3, year: '1508', heritage: true },
      { distanceM: 120 },
    )).toEqual({
      title: 'Dóm sv. Alžbety',
      lines: ['Kostol · Hlavná 1', '3 podlažia · postavené 1508 · pamiatka', '120 m od nehnuteľnosti · ≈ 2 min pešo'],
    }));
  it('the specific type beats the coarse kind', () =>
    expect(buildingInfo({ kind: 'civic', height: 45, type: 'university' }).title).toBe('Univerzita'));
  it('an unknown type falls back to the kind', () =>
    expect(buildingInfo({ kind: 'commercial', height: 8, type: 'car_wash' }).title).toBe('Obchod a služby'));
  it('a named building of unknown type does not show a guessed kind', () =>
    expect(buildingInfo({ kind: 'house', height: 2, name: 'Urbanova veža', address: 'Hlavné námestie 3/1' }).lines)
      .toEqual(['Hlavné námestie 3/1']));
  it('the property does not show its distance to itself', () =>
    expect(buildingInfo({ kind: 'house', height: 6, address: 'Záhradná 12' }, { isProperty: true, distanceM: 0 }).lines)
      .toEqual(['Záhradná 12']));
});
