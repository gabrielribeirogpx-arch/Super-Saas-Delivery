import { apiClient, buildDriverHeaders } from "@/lib/apiClient";

type RequestConfig = {
  url?: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  headers?: Record<string, string>;
  data?: unknown;
  params?: Record<string, string | number | boolean | null | undefined>;
  withCredentials?: boolean;
};

type RequestInterceptor = (config: RequestConfig) => RequestConfig;

type ApiErrorResponse = {
  status: number;
  data: unknown;
};

export class ApiError extends Error {
  response: ApiErrorResponse;

  constructor(message: string, response: ApiErrorResponse) {
    super(message);
    this.name = "ApiError";
    this.response = response;
  }
}

class SimpleAxios {
  interceptors = {
    request: {
      use: (interceptor: RequestInterceptor) => {
        this.requestInterceptor = interceptor;
      },
    },
  };

  private requestInterceptor: RequestInterceptor | null = null;

  async request<T>(config: RequestConfig): Promise<{ data: T }> {
    const parsed = this.requestInterceptor ? this.requestInterceptor(config) : config;

    const rawUrl = parsed.url || "";
    const baseOrigin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
    const urlWithParams = new URL(rawUrl, baseOrigin);

    if (parsed.params) {
      Object.entries(parsed.params).forEach(([key, value]) => {
        if (value === null || typeof value === "undefined") {
          return;
        }
        urlWithParams.searchParams.set(key, String(value));
      });
    }

    const requestUrl = /^https?:\/\//i.test(rawUrl)
      ? urlWithParams.toString()
      : `${urlWithParams.pathname}${urlWithParams.search}`;

    const response = await apiClient(requestUrl, {
      method: parsed.method || "GET",
      headers: buildDriverHeaders({
        "Content-Type": "application/json",
        ...(parsed.headers || {}),
      }),
      body: parsed.data ? JSON.stringify(parsed.data) : undefined,
      credentials: parsed.withCredentials ? "include" : "same-origin",
    });

    const hasJsonBody = response.headers.get("content-type")?.includes("application/json");
    const responseData = hasJsonBody ? await response.json() : null;

    if (!response.ok) {
      throw new ApiError(`Erro na API: ${response.status}`, {
        status: response.status,
        data: responseData,
      });
    }

    const data = responseData as T;
    return { data };
  }

  get<T>(url: string, config: Omit<RequestConfig, "url" | "method"> = {}) {
    return this.request<T>({ ...config, url, method: "GET", withCredentials: true });
  }

  post<T>(url: string, data?: unknown, config: Omit<RequestConfig, "url" | "method" | "data"> = {}) {
    return this.request<T>({ ...config, url, method: "POST", data, withCredentials: true });
  }
}

const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL || "";

function resolveApiBaseUrl() {
  if (!rawBaseUrl) {
    return "";
  }

  const normalizedRawBaseUrl = rawBaseUrl.replace("service-delivery-backand-", "service-delivery-backend-");

  try {
    const parsed = new URL(normalizedRawBaseUrl);
    const normalizedPath = parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/$/, "");
    return `${parsed.origin}${normalizedPath}`;
  } catch {
    return normalizedRawBaseUrl.replace(/\/$/, "");
  }
}

const apiBaseUrl = resolveApiBaseUrl();

function shouldUseSameOriginProxy(normalizedPath: string) {
  if (typeof window === "undefined") {
    return false;
  }

  if (!normalizedPath.startsWith("/api/")) {
    return false;
  }

  return true;
}

function normalizeUrl(path: string) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (shouldUseSameOriginProxy(normalizedPath)) {
    return normalizedPath;
  }

  if (!apiBaseUrl) {
    return normalizedPath;
  }

  if (apiBaseUrl.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${apiBaseUrl}${normalizedPath.slice(4)}`;
  }

  return `${apiBaseUrl}${normalizedPath}`;
}

export const api = new SimpleAxios();

api.interceptors.request.use((config) => ({
  ...config,
  url: config.url ? normalizeUrl(config.url) : config.url,
  headers: Object.fromEntries(buildDriverHeaders(config.headers).entries()),
}));

export { normalizeUrl };
