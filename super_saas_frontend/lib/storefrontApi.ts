const STOREFRONT_API_BASE_URL = "/api";

function sanitizeBaseUrl(url: string) {
  return url.replace(/\/$/, "");
}

export function buildStorefrontApiUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const pathWithoutApiPrefix = normalizedPath.replace(/^\/api(?=\/|$)/, "");
  const cleanPath = pathWithoutApiPrefix.startsWith("/") ? pathWithoutApiPrefix : `/${pathWithoutApiPrefix}`;

  return `${sanitizeBaseUrl(STOREFRONT_API_BASE_URL)}${cleanPath}`;
}

export function resolveStorefrontTenant(tenant?: string | null) {
  const normalizedTenant = tenant?.trim();
  if (normalizedTenant) {
    return normalizedTenant;
  }

  if (typeof window === "undefined") {
    return null;
  }

  const [, tenantFromStoreRoute] = window.location.pathname.match(/\/loja\/([^/]+)/) ?? [];
  if (tenantFromStoreRoute) {
    return decodeURIComponent(tenantFromStoreRoute);
  }

  const [, tenantFromRootRoute] = window.location.pathname.match(/^\/([^/]+)\/mobile(?:\/|$)/) ?? [];
  if (tenantFromRootRoute) {
    return decodeURIComponent(tenantFromRootRoute);
  }

  return null;
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
  const resolvedTenant = resolveStorefrontTenant(tenant);
  const url = new URL(buildStorefrontApiUrl(path), "http://storefront.local");

  if (resolvedTenant && !url.searchParams.has("tenant_id")) {
    url.searchParams.set("tenant_id", resolvedTenant);
  }

  return `${url.pathname}${url.search}`;
}

export async function storefrontFetch(path: string, options: RequestInit = {}, tenant?: string | null) {
  return fetch(buildStorefrontApiUrl(path), {
    ...options,
    headers: buildStorefrontHeaders(options.headers, tenant),
  });
}

export { STOREFRONT_API_BASE_URL };
