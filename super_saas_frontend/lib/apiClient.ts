export function getDriverAuthContext() {
  if (typeof window === "undefined") {
    return { token: null, tenantId: null };
  }

  const storedToken = localStorage.getItem("driver_token") || localStorage.getItem("token");
  const token = storedToken
    ? storedToken.startsWith("Bearer ")
      ? storedToken
      : `Bearer ${storedToken}`
    : null;

  const tenantId = localStorage.getItem("tenant_id");

  return { token, tenantId };
}

export function buildDriverHeaders(headers?: HeadersInit) {
  const normalizedHeaders = new Headers(headers);
  const { token, tenantId } = getDriverAuthContext();

  if (token) {
    normalizedHeaders.set("Authorization", token);
  }

  if (tenantId) {
    normalizedHeaders.set("X-Tenant-ID", tenantId);
  }

  if (typeof window !== "undefined" && !normalizedHeaders.has("x-forwarded-host")) {
    normalizedHeaders.set("x-forwarded-host", window.location.host);
  }

  return normalizedHeaders;
}

export async function apiClient(url: string, options: RequestInit = {}) {
  return fetch(url, {
    cache: "no-store",
    ...options,
    headers: buildDriverHeaders(options.headers),
  });
}
