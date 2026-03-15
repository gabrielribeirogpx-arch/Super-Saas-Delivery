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

export function buildStorefrontWebSocketUrl(path: string) {
  if (typeof window === "undefined") {
    return "";
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL?.trim();

  if (rawBaseUrl) {
    try {
      const parsed = new URL(rawBaseUrl);
      const normalizedPathname = parsed.pathname.replace(/\/+$/, "").replace(/\/api$/, "");
      const protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
      return `${protocol}//${parsed.host}${normalizedPathname}${normalizedPath}`;
    } catch {
      // fallback para mesma origem da página
    }
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${normalizedPath}`;
}

export { STOREFRONT_API_BASE_URL };
