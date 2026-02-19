export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

const RAW_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://service-delivery-backend-production.up.railway.app";

// Remove barra final se existir
const baseUrl = RAW_BASE_URL.replace(/\/$/, "");

export async function apiFetch(
  url: string,
  options: RequestInit = {}
) {
  // Se já vier URL absoluta, não prefixar
  const finalUrl = url.startsWith("http")
    ? url
    : `${baseUrl}${url}`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  let body = options.body;

  if (
    body &&
    typeof body !== "string" &&
    !(body instanceof FormData)
  ) {
    body = JSON.stringify(body);
  }

  if (body instanceof FormData) {
    delete (headers as any)["Content-Type"];
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
  options: RequestInit = {}
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
      body: body as BodyInit | null | undefined,
    }),
  put: <T>(path: string, body?: unknown, headers?: HeadersInit) =>
    request<T>(path, {
      method: "PUT",
      headers,
      body: body as BodyInit | null | undefined,
    }),
  patch: <T>(path: string, body?: unknown, headers?: HeadersInit) =>
    request<T>(path, {
      method: "PATCH",
      headers,
      body: body as BodyInit | null | undefined,
    }),
  delete: <T>(path: string, headers?: HeadersInit) =>
    request<T>(path, {
      method: "DELETE",
      headers,
    }),
};

export { baseUrl };
