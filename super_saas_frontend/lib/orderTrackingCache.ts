"use client";

type CachedTrackingOrder = {
  token: string;
  tenant?: string | null;
  orderNumber?: number | null;
  totalCents?: number | null;
  paymentMethod?: string | null;
  deliveryType?: string | null;
  status?: string | null;
  createdAt: number;
};

const STORAGE_PREFIX = "storefront:tracking-order:";
const LATEST_ORDER_PREFIX = "storefront:tracking-order:latest:";
const MAX_CACHE_AGE_MS = 30 * 60 * 1000;

function normalizeToken(token: string | null | undefined) {
  const normalized = String(token || "").trim();
  return normalized || null;
}

function isBrowser() {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

function safeRead(key: string) {
  if (!isBrowser()) {
    return null;
  }

  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWrite(key: string, value: string) {
  if (!isBrowser()) {
    return;
  }

  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // ignorar indisponibilidade de storage
  }
}

function safeRemove(key: string) {
  if (!isBrowser()) {
    return;
  }

  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // ignorar indisponibilidade de storage
  }
}

function parseCachedOrder(rawValue: string | null): CachedTrackingOrder | null {
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as CachedTrackingOrder;
    const token = normalizeToken(parsed?.token);
    const createdAt = Number(parsed?.createdAt);

    if (!token || !Number.isFinite(createdAt)) {
      return null;
    }

    if (Date.now() - createdAt > MAX_CACHE_AGE_MS) {
      return null;
    }

    return {
      ...parsed,
      token,
      createdAt,
    };
  } catch {
    return null;
  }
}

export function cacheTrackingOrder(order: Omit<CachedTrackingOrder, "createdAt">) {
  const token = normalizeToken(order.token);
  if (!token) {
    return;
  }

  const payload: CachedTrackingOrder = {
    ...order,
    token,
    createdAt: Date.now(),
  };

  safeWrite(`${STORAGE_PREFIX}${token}`, JSON.stringify(payload));

  if (order.tenant) {
    safeWrite(`${LATEST_ORDER_PREFIX}${order.tenant}`, token);
  }
}

export function getCachedTrackingOrder(token: string | null | undefined) {
  const normalizedToken = normalizeToken(token);
  if (!normalizedToken) {
    return null;
  }

  const key = `${STORAGE_PREFIX}${normalizedToken}`;
  const cached = parseCachedOrder(safeRead(key));
  if (!cached) {
    safeRemove(key);
  }
  return cached;
}

export function getLatestCachedTrackingOrder(tenant: string | null | undefined) {
  const normalizedTenant = String(tenant || "").trim();
  if (!normalizedTenant) {
    return null;
  }

  const latestToken = normalizeToken(safeRead(`${LATEST_ORDER_PREFIX}${normalizedTenant}`));
  return getCachedTrackingOrder(latestToken);
}
