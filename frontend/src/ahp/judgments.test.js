import { describe, expect, it } from 'vitest';
import { formatCr, judgmentFor, positionLabel, worstPair } from './judgments.js';

const LABELS = { 1: 'rovnako dôležité', 3: 'mierne dôležitejšie', 5: 'výrazne dôležitejšie', 7: 'veľmi výrazne dôležitejšie', 9: 'extrémne dôležitejšie' };

describe('judgments', () => {
  it('maps positions to Saaty values from the left criterion', () => {
    expect([-4, -1, 0, 1, 4].map(judgmentFor)).toEqual([9, 3, 1, 1 / 3, 1 / 9]);
  });
  it('words a position', () => {
    expect(positionLabel(-2, 'Škôlka', 'Ihrisko', LABELS)).toBe('Škôlka je výrazne dôležitejšie');
    expect(positionLabel(0, 'Škôlka', 'Ihrisko', LABELS)).toBe('Škôlka a Ihrisko sú rovnako dôležité');
  });
  it('finds the comparison that contradicts the others most', () => {
    const weights = { a: 4 / 7, b: 2 / 7, c: 1 / 7 };
    expect(worstPair({ 'a|b': 2, 'a|c': 1 / 4, 'b|c': 2 }, weights)).toBe('a|c');
    expect(formatCr(0.1449)).toBe('0,14');
  });
});
