// Demand-test bookkeeping: which price this visitor sees and which ad brought them. No cookies.

const TAG = /^[\w.-]{1,60}$/;

/** `?cena=19` forces a variant (to check each one); otherwise keep the session's, else pick at random. */
export function pickVariant(variants, { forced = null, stored = null, random = Math.random } = {}) {
  if (!variants?.length) return null;
  if (forced && variants.includes(forced)) return forced;
  if (stored && variants.includes(stored)) return stored;
  return variants[Math.floor(random() * variants.length) % variants.length];
}

/** utm_source / utm_campaign from the landing URL, falling back to what this session already saw. */
export function readTags(search, stored = {}) {
  const p = new URLSearchParams(search);
  const clean = (v) => (v && TAG.test(v) ? v : null);
  return {
    source: clean(p.get('utm_source')) ?? stored.source ?? null,
    campaign: clean(p.get('utm_campaign')) ?? stored.campaign ?? null,
  };
}

export function priceLabel(variant) {
  return variant ? `Správa za ${variant} €` : 'Správa za pár eur';
}

/** The listing URL someone typed, if it looks like one (sent along with the sign-up). */
export function listingUrl(raw) {
  const s = String(raw ?? '').trim();
  return /^https?:\/\/\S+$/.test(s) && s.length <= 500 ? s : null;
}
