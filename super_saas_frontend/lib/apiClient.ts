import { getDriverTenantId, getDriverToken, isDriverTokenExpired, redirectToDriverLogin } from "@/lib/driverAuth";

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

  if (token) {
    normalizedHeaders.set("Authorization", `Bearer ${token.replace(/^Bearer\s+/i, "")}`);
  } else if (!normalizedHeaders.get("Authorization")?.trim()) {
    normalizedHeaders.delete("Authorization");
  }

  if (tenantId) {
    normalizedHeaders.set("X-Tenant-ID", tenantId);
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

export async function apiClient(url: string, options: RequestInit = {}) {
  if (isDriverTokenExpired()) {
    redirectToDriverLogin();
    throw new Error("Sessão expirada");
  }

  const response = await fetch(url, {
    ...options,
    credentials: "include",
    cache: "no-store",
    headers: buildDriverHeaders(options.headers, options.body),
  });

  const isDriverLoginRequest = String(url).includes("/api/driver/auth/login");
  if (!isDriverLoginRequest && (response.status === 401 || response.status === 403)) {
    redirectToDriverLogin();
  }

  return response;
}
