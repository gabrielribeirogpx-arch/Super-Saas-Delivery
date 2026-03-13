const API_BASE_URL = "https://service-delivery-backend-production.up.railway.app";

function sanitizeBaseUrl(url: string) {
  return url.replace(/\/$/, "");
}

export function buildStorefrontApiUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${sanitizeBaseUrl(API_BASE_URL)}${normalizedPath}`;
}

export { API_BASE_URL };
