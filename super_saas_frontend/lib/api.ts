export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

type ApiFetchOptions = Omit<RequestInit, "body"> & {
  body?: any;
};

const RAW_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

const baseUrl = RAW_BASE_URL.replace(/\/$/, "");

const TENANT_REQUIRED_PREFIXES = [
  "/api/admin",
  "/api/dashboard",
  "/api/finance",
  "/api/reports",
  "/api/inventory",
  "/api/kds",
  "/api/orders",
  "/api/admin/menu",
];

let cachedTenantId: number | undefined;
let tenantIdRequest: Promise<number | null> | null = null;

function joinApiUrl(path: string) {
  if (!baseUrl) {
    return path;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  // Evita duplicação de prefixo quando NEXT_PUBLIC_API_URL termina em /api
  // e o endpoint também começa com /api.
  if (baseUrl.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${baseUrl}${normalizedPath.slice(4)}`;
  }

  return `${baseUrl}${normalizedPath}`;
}

function shouldAttachTenantId(pathname: string) {
  return TENANT_REQUIRED_PREFIXES.some((prefix) =>
    pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

async function resolveTenantId() {
  if (cachedTenantId !== undefined) {
    return cachedTenantId;
  }

  if (tenantIdRequest) {
    return tenantIdRequest;
  }

  tenantIdRequest = (async () => {
    try {
      const response = await fetch(joinApiUrl("/api/admin/auth/me"), {
        credentials: "include",
      });

      if (!response.ok) {
        return null;
      }

      const data = (await response.json()) as { tenant_id?: unknown };
      const tenantId = Number(data?.tenant_id);

      if (!Number.isFinite(tenantId)) {
        return null;
      }

      cachedTenantId = tenantId;
      return tenantId;
    } catch {
      return null;
    } finally {
      tenantIdRequest = null;
    }
  })();

  return tenantIdRequest;
}

async function withTenantId(url: string) {
  if (typeof window === "undefined") {
    return url;
  }

  const parsed = new URL(url, window.location.origin);

  if (!shouldAttachTenantId(parsed.pathname) || parsed.searchParams.has("tenant_id")) {
    return url;
  }

  const tenantId = await resolveTenantId();
  if (!tenantId) {
    return url;
  }

  parsed.searchParams.set("tenant_id", String(tenantId));

  if (url.startsWith("http")) {
    return parsed.toString();
  }

  return `${parsed.pathname}${parsed.search}`;
}

export async function apiFetch(
  url: string,
  options: ApiFetchOptions = {}
) {
  const baseFinalUrl = url.startsWith("http") ? url : joinApiUrl(url);
  const finalUrl = await withTenantId(baseFinalUrl);

  const headers = new Headers();

  headers.set("Content-Type", "application/json");

  if (options.headers) {
    Object.entries(options.headers as Record<string, string>).forEach(
      ([key, value]) => {
        headers.set(key, value);
      }
    );
  }

  if (typeof window !== "undefined" && !headers.has("x-forwarded-host")) {
    headers.set("x-forwarded-host", window.location.host);
  }

  let body = options.body;

  if (
    body &&
    typeof body !== "string" &&
    !(body instanceof FormData)
  ) {
    body = JSON.stringify(body);
  }

  if (body instanceof FormData) {
    headers.delete("Content-Type");
  }

  return fetch(finalUrl, {
    ...options,
    headers,
    body,
    credentials: "include"
  });
}

async function request<T>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const response = await apiFetch(path, options);

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      typeof data === "string"
        ? data
        : (data as { detail?: string })?.detail || "Erro inesperado";
    throw new ApiError(message, response.status, data);
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, headers?: HeadersInit) => request<T>(path, { headers }),
  post: <T>(path: string, body?: unknown, headers?: HeadersInit) =>
    request<T>(path, {
      method: "POST",
      headers,
      body,
    }),
  put: <T>(path: string, body?: unknown, headers?: HeadersInit) =>
    request<T>(path, {
      method: "PUT",
      headers,
      body,
    }),
  patch: <T>(path: string, body?: unknown, headers?: HeadersInit) =>
    request<T>(path, {
      method: "PATCH",
      headers,
      body,
    }),
  delete: <T>(path: string, headers?: HeadersInit) =>
    request<T>(path, {
      method: "DELETE",
      headers,
    }),
};

export { baseUrl };
