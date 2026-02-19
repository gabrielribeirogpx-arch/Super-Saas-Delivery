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

export async function apiFetch(
  url: string,
  options: ApiFetchOptions = {}
) {
  const finalUrl = url.startsWith("http")
    ? url
    : baseUrl
      ? `${baseUrl}${url}`
      : url;

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
