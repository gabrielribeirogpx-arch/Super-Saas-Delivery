import { getDriverTenantId, getDriverToken, isDriverTokenExpired, redirectToDriverLogin } from "@/lib/driverAuth";
import { getTenantSlugFromCurrentHostname } from "@/lib/tenant";

export function getDriverAuthContext() {
  if (typeof window === "undefined") {
    return { token: null, tenantId: null };
  }

  const token = getDriverToken();
  const tenantId = getDriverTenantId();

  return { token, tenantId };
}

export function buildDriverHeaders(headers?: HeadersInit, body?: BodyInit | null) {
  const normalizedHeaders = new Headers(headers);
  const { token, tenantId } = getDriverAuthContext();
  const tenantSlug = getTenantSlugFromCurrentHostname();

  if (token) {
    normalizedHeaders.set("Authorization", `Bearer ${token.replace(/^Bearer\s+/i, "")}`);
  } else if (!normalizedHeaders.get("Authorization")?.trim()) {
    normalizedHeaders.delete("Authorization");
  }

  if (tenantSlug) {
    normalizedHeaders.set("X-Tenant-Slug", tenantSlug);
  } else if (!normalizedHeaders.get("X-Tenant-Slug")?.trim()) {
    normalizedHeaders.delete("X-Tenant-Slug");
  }

  if (tenantId) {
    normalizedHeaders.set("X-Tenant-ID", tenantId);
  } else if (tenantSlug) {
    normalizedHeaders.set("X-Tenant-ID", tenantSlug);
  } else if (!normalizedHeaders.get("X-Tenant-ID")?.trim()) {
    normalizedHeaders.delete("X-Tenant-ID");
  }

  if (body instanceof FormData) {
    normalizedHeaders.delete("Content-Type");
  } else if (!normalizedHeaders.has("Content-Type")) {
    normalizedHeaders.set("Content-Type", "application/json");
  }

  return normalizedHeaders;
}

function isDriverApiRequest(url: string) {
  try {
    return new URL(url, typeof window === "undefined" ? "http://localhost" : window.location.origin).pathname.startsWith("/api/driver/");
  } catch {
    return String(url).includes("/api/driver/");
  }
}

export async function apiClient(url: string, options: RequestInit = {}) {
  const path = new URL(url, typeof window === "undefined" ? "http://localhost" : window.location.origin).pathname;
  const isPublicDriverAuthRequest = ["/api/driver/auth/login", "/api/driver/auth/forgot-password", "/api/driver/auth/reset-password"].includes(path);
  const isDriverRequest = isDriverApiRequest(String(url));

  if (!isPublicDriverAuthRequest && isDriverRequest && !getDriverToken()) {
    redirectToDriverLogin();
    throw new Error("Sessão do entregador ausente");
  }

  if (!isPublicDriverAuthRequest && isDriverRequest && isDriverTokenExpired()) {
    redirectToDriverLogin();
    throw new Error("Sessão expirada");
  }

  const headers = buildDriverHeaders(options.headers, options.body);
  if (isPublicDriverAuthRequest) {
    // Public recovery must work even with an expired session from another store.
    headers.delete("Authorization");
    headers.delete("X-Tenant-ID");
  }
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    cache: "no-store",
    headers,
  });

  if (!isPublicDriverAuthRequest && isDriverRequest && (response.status === 401 || response.status === 403)) {
    redirectToDriverLogin();
  }

  return response;
}
