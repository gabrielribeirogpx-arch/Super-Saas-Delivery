import {
  extractPlatformTenantSlug,
  normalizeHostname,
  normalizePlatformBaseDomain,
  RESERVED_PLATFORM_SUBDOMAINS,
} from "./platformDomains";

const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export const tenantPath = (_tenantId: string | number, path: string) =>
  `${path.startsWith("/") ? path : `/${path}`}`;

export function normalizePublicBaseDomain(baseDomain?: string | null) {
  return normalizePlatformBaseDomain(baseDomain || "servicedelivery.com.br");
}

export function isValidTenantSlug(slug?: string | null) {
  return Boolean(slug && TENANT_SLUG_PATTERN.test(slug));
}

export function extractTenantSlugFromHostname(
  hostname?: string | null,
  baseDomain?: string | null
) {
  const candidate = baseDomain
    ? extractTenantSlugForBase(hostname, baseDomain)
    : extractPlatformTenantSlug(hostname);
  return isValidTenantSlug(candidate) ? candidate : null;
}

function extractTenantSlugForBase(hostname?: string | null, baseDomain?: string | null) {
  const normalizedHostname = normalizeHostname(hostname);
  const normalizedBase = normalizePlatformBaseDomain(baseDomain);
  const suffix = `.${normalizedBase}`;
  if (!normalizedBase || !normalizedHostname.endsWith(suffix)) return null;
  const candidate = normalizedHostname.slice(0, -suffix.length).split(".").filter(Boolean).at(-1);
  return candidate && !RESERVED_PLATFORM_SUBDOMAINS.has(candidate) ? candidate : null;
}

export { normalizeHostname };

export function getTenantSlugFromCurrentHostname() {
  if (typeof window === "undefined") return null;
  return extractTenantSlugFromHostname(window.location.hostname);
}
