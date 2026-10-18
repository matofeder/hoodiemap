// The questionnaire's arithmetic. Positions run from -4 (left much more important) to +4 (right much more).
export const POSITIONS = [-4, -3, -2, -1, 0, 1, 2, 3, 4];
const SAATY = { 0: 1, 1: 3, 2: 5, 3: 7, 4: 9 };

/** Position -> judgment "A|B" (how much more important the left criterion A is than B). */
export function judgmentFor(position) {
  const v = SAATY[Math.abs(position)];
  return position <= 0 ? v : 1 / v;
}

export function positionLabel(position, left, right, labels) {
  if (position === 0) return `${left} a ${right} sú ${labels[1]}`;
  const v = SAATY[Math.abs(position)];
  return `${position < 0 ? left : right} je ${labels[v]}`;
}

/** The comparison furthest from what the weights imply: the first one an expert should look at again. */
export function worstPair(judgments, weights) {
  let worst = null;
  for (const [key, value] of Object.entries(judgments)) {
    const [a, b] = key.split('|');
    const implied = weights[a] / weights[b];
    const off = Math.abs(Math.log(value / implied));
    if (!worst || off > worst.off) worst = { key, off };
  }
  return worst?.key ?? null;
}

export function formatCr(cr) {
  return cr.toFixed(2).replace('.', ',');
}
