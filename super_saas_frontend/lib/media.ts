import { baseUrl } from "@/lib/api";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);

export function resolveMediaUrl(url?: string | null): string | null {
  if (!url) return null;

  const value = url.trim();
  if (!value) return null;

  if (value.startsWith("data:") || value.startsWith("blob:")) {
    return value;
  }

  const fallbackBase =
    typeof window !== "undefined" ? window.location.origin : undefined;

  if (value.startsWith("http://") || value.startsWith("https://")) {
    try {
      const parsed = new URL(value);
      if (parsed.pathname.startsWith("/uploads") && LOCAL_HOSTS.has(parsed.hostname)) {
        const preferredBase = baseUrl || fallbackBase;
        return preferredBase ? new URL(`${parsed.pathname}${parsed.search}`, preferredBase).toString() : value;
      }
      return value;
    } catch {
      return value;
    }
  }

  const preferredBase = baseUrl || fallbackBase;

  if (!preferredBase) {
    return value.startsWith("/") ? value : `/${value}`;
  }

  try {
    return new URL(value, preferredBase).toString();
  } catch {
    return value;
  }
}
