const DEFAULT_PLATFORM_BASE_DOMAINS = ["servicedelivery.com.br", "fomizero.com.br"];

export const RESERVED_PLATFORM_SUBDOMAINS = new Set([
  "www",
  "app",
  "api",
  "admin",
  "mail",
  "status",
  "support",
  "help",
  "docs",
  "cdn",
  "assets",
  "static",
  "auth",
  "billing",
  "webhook",
  "m",
]);

export function normalizeHostname(hostname?: string | null) {
  const raw = (hostname || "").split(",")[0].trim().toLowerCase();
  if (!raw) return "";

  try {
    if (raw.includes("://")) return new URL(raw).hostname.toLowerCase();
  } catch {
    return "";
  }

  return raw.split("/")[0].replace(/:\d+$/, "").replace(/^\.+|\.+$/g, "");
}

export function normalizePlatformBaseDomain(value?: string | null) {
  return normalizeHostname((value || "").replace(/^\*\./, ""));
}

export function getPlatformBaseDomains() {
  const canonical = process.env.NEXT_PUBLIC_PLATFORM_BASE_DOMAINS;
  const configured = canonical ? canonical.split(",") : DEFAULT_PLATFORM_BASE_DOMAINS;
  const candidates = [
    ...configured,
    process.env.NEXT_PUBLIC_BASE_DOMAIN,
    process.env.NEXT_PUBLIC_PUBLIC_BASE_DOMAIN,
  ];

  return candidates.reduce<string[]>((domains, candidate) => {
    const normalized = normalizePlatformBaseDomain(candidate);
    if (normalized && !domains.includes(normalized)) domains.push(normalized);
    return domains;
  }, []);
}

export function extractPlatformTenantSlug(hostname?: string | null) {
  const normalizedHostname = normalizeHostname(hostname);
  if (!normalizedHostname) return null;

  for (const baseDomain of getPlatformBaseDomains()) {
    const suffix = `.${baseDomain}`;
    if (!normalizedHostname.endsWith(suffix)) continue;

    const prefix = normalizedHostname.slice(0, -suffix.length);
    const labels = prefix.split(".").filter(Boolean);
    const candidate = labels.at(-1);
    if (!candidate || RESERVED_PLATFORM_SUBDOMAINS.has(candidate)) return null;
    return candidate;
  }

  return null;
}
