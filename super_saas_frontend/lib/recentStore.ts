// Only an address hint. No session, password, checkout URL, payment claim or token.
const KEY = "fomizero:recent-store:v1";
export function rememberStore(slug: string) {
  if (!/^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])?$/.test(slug)) return;
  try { localStorage.setItem(KEY, slug); } catch { /* Storage is optional. */ }
}
export function recentStore(): string {
  try {
    const value = localStorage.getItem(KEY) ?? "";
    return /^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])?$/.test(value) ? value : "";
  } catch { return ""; }
}
