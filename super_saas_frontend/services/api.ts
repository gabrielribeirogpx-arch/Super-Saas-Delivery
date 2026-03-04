type RequestConfig = {
  url?: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  headers?: Record<string, string>;
  data?: unknown;
  withCredentials?: boolean;
};

type RequestInterceptor = (config: RequestConfig) => RequestConfig;

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

    const response = await fetch(parsed.url || "", {
      method: parsed.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(parsed.headers || {}),
      },
      body: parsed.data ? JSON.stringify(parsed.data) : undefined,
      credentials: parsed.withCredentials ? "include" : "same-origin",
    });

    if (!response.ok) {
      throw new Error(`Erro na API: ${response.status}`);
    }

    const data = (await response.json()) as T;
    return { data };
  }

  get<T>(url: string) {
    return this.request<T>({ url, method: "GET", withCredentials: true });
  }

  post<T>(url: string, data?: unknown) {
    return this.request<T>({ url, method: "POST", data, withCredentials: true });
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
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };
});

export { normalizeUrl };
