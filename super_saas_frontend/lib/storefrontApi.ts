const STOREFRONT_API_BASE_URL = process.env.NEXT_PUBLIC_STOREFRONT_API_BASE_URL || "";

function sanitizeBaseUrl(url: string) {
  return url.replace(/\/$/, "");
}

export function buildStorefrontApiUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (!STOREFRONT_API_BASE_URL) {
    return normalizedPath;
  }

  return `${sanitizeBaseUrl(STOREFRONT_API_BASE_URL)}${normalizedPath}`;
}

export { STOREFRONT_API_BASE_URL };
