import { describe, expect, it } from 'vitest';
import { createRequestGate } from './requestGate.js';

describe('createRequestGate', () => {
  it('only the latest token is current', () => {
    const gate = createRequestGate();
    const a = gate.next();
    const b = gate.next();
    expect(gate.isCurrent(a)).toBe(false);
    expect(gate.isCurrent(b)).toBe(true);
  });
});
