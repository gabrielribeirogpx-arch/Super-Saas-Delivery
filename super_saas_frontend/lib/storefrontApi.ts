const STOREFRONT_API_BASE_URL = "/api";
const URL_PARSE_BASE = "http://storefront.local";

function sanitizeBaseUrl(url: string) {
  return url.replace(/\/$/, "");
}

function normalizeTenantCandidate(value?: string | null) {
  const normalized = value?.trim();
  return normalized ? decodeURIComponent(normalized) : null;
}

function resolveTenantFromPathname(pathname: string) {
  const pathCandidates = [
    pathname.match(/\/loja\/([^/]+)/),
    pathname.match(/^\/([^/]+)\/mobile(?:\/|$)/),
  ];

  for (const match of pathCandidates) {
    const tenant = normalizeTenantCandidate(match?.[1]);
    if (tenant) {
      return tenant;
    }
  }

  return null;
}

function resolveTenantFromHost(hostname: string) {
  const normalizedHost = hostname.trim().toLowerCase();
  if (!normalizedHost || normalizedHost === "localhost") {
    return null;
  }

  const labels = normalizedHost.split(".").filter(Boolean);
  if (labels.length < 3) {
    return null;
  }

  const candidate = labels[0];
  if (!candidate || candidate === "www" || candidate === "m") {
    return null;
  }

  return normalizeTenantCandidate(candidate);
}

export function buildStorefrontApiUrl(path: string, tenant?: string | null) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const pathWithoutApiPrefix = normalizedPath.replace(/^\/api(?=\/|$)/, "");
  const cleanPath = pathWithoutApiPrefix.startsWith("/") ? pathWithoutApiPrefix : `/${pathWithoutApiPrefix}`;
  const url = new URL(`${sanitizeBaseUrl(STOREFRONT_API_BASE_URL)}${cleanPath}`, URL_PARSE_BASE);
  const resolvedTenant = resolveStorefrontTenant(tenant);

  if (resolvedTenant && !url.searchParams.has("tenant") && !url.searchParams.has("tenant_id")) {
    url.searchParams.set("tenant", resolvedTenant);
  }

  return `${url.pathname}${url.search}`;
}

export function resolveStorefrontTenant(tenant?: string | null) {
  const normalizedTenant = normalizeTenantCandidate(tenant);
  if (normalizedTenant) {
    return normalizedTenant;
  }

  if (typeof window === "undefined") {
    return null;
  }

  return resolveTenantFromPathname(window.location.pathname) || resolveTenantFromHost(window.location.hostname);
}

export function requireStorefrontTenant(tenant?: string | null) {
  const resolvedTenant = resolveStorefrontTenant(tenant);
  if (!resolvedTenant) {
    throw new Error("Tenant could not be resolved for storefront request");
  }
  return resolvedTenant;
}

export function buildStorefrontHeaders(headers?: HeadersInit, tenant?: string | null) {
  const normalizedHeaders = new Headers(headers);
  const resolvedTenant = resolveStorefrontTenant(tenant);

  if (resolvedTenant) {
    normalizedHeaders.set("x-tenant-id", resolvedTenant);
  }

  return normalizedHeaders;
}

export function buildStorefrontEventStreamUrl(path: string, tenant?: string | null) {
  return buildStorefrontApiUrl(path, tenant);
}

export async function storefrontFetch(path: string, options: RequestInit = {}, tenant?: string | null) {
  return fetch(buildStorefrontApiUrl(path, tenant), {
    ...options,
    headers: buildStorefrontHeaders(options.headers, tenant),
  });
}

export { STOREFRONT_API_BASE_URL, resolveTenantFromHost, resolveTenantFromPathname };
