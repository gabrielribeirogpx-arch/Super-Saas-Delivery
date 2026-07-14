const DEFAULT_PUBLIC_BASE_DOMAIN = "servicedelivery.com.br";
const RESERVED_SUBDOMAINS = new Set(["www"]);
const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export const tenantPath = (_tenantId: string | number, path: string) =>
  `${path.startsWith("/") ? path : `/${path}`}`;

export function normalizePublicBaseDomain(baseDomain?: string | null) {
  return (baseDomain || DEFAULT_PUBLIC_BASE_DOMAIN)
    .replace(/^https?:\/\//i, "")
    .replace(/^\*\./, "")
    .replace(/[:/].*$/, "")
    .toLowerCase()
    .trim()
    .replace(/^\.+|\.+$/g, "");
}

export function normalizeHostname(hostname?: string | null) {
  const raw = (hostname || "").split(",")[0].trim().toLowerCase();
  if (!raw) return "";

  try {
    if (raw.includes("://")) {
      return new URL(raw).hostname.toLowerCase();
    }
  } catch {
    return "";
  }

  return raw.split("/")[0].replace(/:\d+$/, "").replace(/^\.+|\.+$/g, "");
}

export function isValidTenantSlug(slug?: string | null) {
  return Boolean(slug && TENANT_SLUG_PATTERN.test(slug));
}

export function extractTenantSlugFromHostname(
  hostname?: string | null,
  baseDomain = process.env.NEXT_PUBLIC_PUBLIC_BASE_DOMAIN
) {
  const normalizedHostname = normalizeHostname(hostname);
  const normalizedBaseDomain = normalizePublicBaseDomain(baseDomain);

  if (!normalizedHostname || !normalizedBaseDomain) return null;
  if (normalizedHostname === normalizedBaseDomain) return null;

  const suffix = `.${normalizedBaseDomain}`;
  if (!normalizedHostname.endsWith(suffix)) return null;

  const prefix = normalizedHostname.slice(0, -suffix.length);
  if (!prefix || prefix.includes(".")) return null;
  if (RESERVED_SUBDOMAINS.has(prefix)) return null;

  return isValidTenantSlug(prefix) ? prefix : null;
}

export function getTenantSlugFromCurrentHostname() {
  if (typeof window === "undefined") return null;
  return extractTenantSlugFromHostname(window.location.hostname);
}
