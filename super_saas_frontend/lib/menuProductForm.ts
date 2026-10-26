export function parseMenuPriceCents(raw: string): number | null {
  const text = raw.trim().replace(/^R\$\s*/, "").replace(/\s/g, "");
  if (!text) return null;

  const normalized = /^\d{1,3}(?:\.\d{3})+,\d{1,2}$/.test(text)
    ? text.replace(/\./g, "").replace(",", ".")
    : text.replace(",", ".");
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;

  const cents = Math.round(Number(normalized) * 100);
  return Number.isSafeInteger(cents) && cents >= 0 ? cents : null;
}
