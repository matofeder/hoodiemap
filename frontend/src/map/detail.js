// What each tier draws. Bigger maps drop the small, per-object details — they would be
// invisible at that scale and cost the most draw calls.
const DETAIL = {
  address: { lanes: true, decor: true, people: 1, pigeons: true, seededTrees: true, maxCars: 6, shadowMap: 1024, property: true, streetFocus: false },
  street: { lanes: true, decor: false, people: 0.5, pigeons: false, seededTrees: true, maxCars: 6, shadowMap: 2048, property: false, streetFocus: true },
  city: { lanes: false, decor: false, people: 0, pigeons: false, seededTrees: false, maxCars: 10, shadowMap: 2048, property: false, streetFocus: false },
};

export function detailFor(tier) {
  return DETAIL[tier] ?? DETAIL.address;
}
