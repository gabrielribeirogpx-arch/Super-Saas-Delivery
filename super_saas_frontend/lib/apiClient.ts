export function getDriverAuthContext() {
  if (typeof window === "undefined") {
    return { token: null, tenantId: null };
  }

  const token =
    localStorage.getItem("driver_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("access_token");
  const tenantId = localStorage.getItem("tenant_id") || extractTenantFromToken(token);

  return { token, tenantId };
}

function extractTenantFromToken(token: string | null): string | null {
  if (!token) {
    return null;
  }

  const rawToken = token.replace(/^Bearer\s+/i, "").trim();
  if (!rawToken) {
    return null;
  }

  const tokenParts = rawToken.split(".");
  if (tokenParts.length < 2) {
    return null;
  }

  const payloadPart = tokenParts[1];

  try {
    const normalizedBase64 = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const paddedBase64 = normalizedBase64.padEnd(Math.ceil(normalizedBase64.length / 4) * 4, "=");
    const payloadText = atob(paddedBase64);
    const payload = JSON.parse(payloadText) as { tenant_id?: number | string; tenant_slug?: string };

    if (payload.tenant_id !== undefined && payload.tenant_id !== null) {
      return String(payload.tenant_id);
    }

    if (payload.tenant_slug) {
      return payload.tenant_slug;
    }

    return null;
  } catch {
    return null;
  }
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
  return fetch(url, {
    ...options,
    credentials: "include",
    cache: "no-store",
    headers: buildDriverHeaders(options.headers, options.body),
  });
}
