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

    const response = await fetch(requestUrl, {
      method: parsed.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(parsed.headers || {}),
      },
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
const apiBaseUrl = rawBaseUrl.replace(/\/$/, "");

function normalizeUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (!apiBaseUrl) {
    return normalizedPath;
  }

  if (apiBaseUrl.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${apiBaseUrl}${normalizedPath.slice(4)}`;
  }

  return `${apiBaseUrl}${normalizedPath}`;
}

export const api = new SimpleAxios();

api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("driver_token") : null;

  return {
    ...config,
    url: config.url ? normalizeUrl(config.url) : config.url,
    headers: {
      ...(config.headers || {}),
      ...(token ? { Authorization: token.startsWith("Bearer ") ? token : `Bearer ${token}` } : {}),
    },
  };
});

export { normalizeUrl };
