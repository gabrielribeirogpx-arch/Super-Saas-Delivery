const STOREFRONT_API_BASE_URL = "/api";

function sanitizeBaseUrl(url: string) {
  return url.replace(/\/$/, "");
}

export function buildStorefrontApiUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${sanitizeBaseUrl(STOREFRONT_API_BASE_URL)}${normalizedPath}`;
}

export { STOREFRONT_API_BASE_URL };
