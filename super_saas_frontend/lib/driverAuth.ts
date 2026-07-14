export const DRIVER_TOKEN_KEY = "driver_token";
export const DRIVER_SESSION_COOKIE = "driver_session";

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

function isBrowser() {
  return typeof window !== "undefined";
}

export function getDriverToken() {
  if (!isBrowser()) return null;
  return localStorage.getItem(DRIVER_TOKEN_KEY);
}

function decodeJwtPayload(token: string | null): Record<string, unknown> | null {
  if (!token) return null;
  const rawToken = token.replace(/^Bearer\s+/i, "").trim();
  const payloadPart = rawToken.split(".")[1];
  if (!payloadPart) return null;

  try {
    const normalizedBase64 = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const paddedBase64 = normalizedBase64.padEnd(Math.ceil(normalizedBase64.length / 4) * 4, "=");
    return JSON.parse(atob(paddedBase64)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function getDriverTenantId() {
  const payload = decodeJwtPayload(getDriverToken());
  const tenantId = payload?.tenant_id ?? payload?.restaurant_id;
  return tenantId === undefined || tenantId === null ? null : String(tenantId);
}

export function isDriverTokenExpired(token = getDriverToken()) {
  const payload = decodeJwtPayload(token);
  const exp = Number(payload?.exp);
  return Number.isFinite(exp) && Date.now() >= exp * 1000;
}

export function hasDriverSession() {
  const token = getDriverToken();
  return Boolean(token) && !isDriverTokenExpired(token);
}

export function saveDriverSession(token: string) {
  if (!isBrowser()) return;
  const cleanToken = token.replace(/^Bearer\s+/i, "").trim();
  localStorage.setItem(DRIVER_TOKEN_KEY, cleanToken);
  document.cookie = `${DRIVER_SESSION_COOKIE}=1; Path=/driver; Max-Age=${COOKIE_MAX_AGE_SECONDS}; SameSite=Lax${window.location.protocol === "https:" ? "; Secure" : ""}`;
}

export function clearDriverSession() {
  if (!isBrowser()) return;
  window.dispatchEvent(new CustomEvent("driver:session-cleared"));
  localStorage.removeItem(DRIVER_TOKEN_KEY);
  localStorage.removeItem("tenant_id");
  document.cookie = `${DRIVER_SESSION_COOKIE}=; Path=/driver; Max-Age=0; SameSite=Lax${window.location.protocol === "https:" ? "; Secure" : ""}`;
}

export function redirectToDriverLogin() {
  if (!isBrowser()) return;
  clearDriverSession();
  const next = `${window.location.pathname}${window.location.search}`;
  const target = next && next !== "/driver/login" ? `/driver/login?next=${encodeURIComponent(next)}` : "/driver/login";
  window.location.replace(target);
}
