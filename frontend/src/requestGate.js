// "Latest request wins": a newer search makes every older token stale.
export function createRequestGate() {
  let current = 0;
  return {
    next: () => ++current,
    isCurrent: (token) => token === current,
  };
}
