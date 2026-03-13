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

export { STOREFRONT_API_BASE_URL };
