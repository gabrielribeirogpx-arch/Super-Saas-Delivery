"use client";

export type CachedTrackingOrder = {
  token: string;
  tenant?: string | null;
  orderNumber?: number | null;
  totalCents?: number | null;
  subtotalCents?: number | null;
  deliveryFeeCents?: number | null;
  pointsEarned?: number | null;
  paymentMethod?: string | null;
  deliveryType?: string | null;
  status?: string | null;
  createdAt: number;
};

const STORAGE_PREFIX = "storefront:tracking-order:";
const SNAPSHOT_PREFIX = "storefront:tracking-snapshot:";
const LATEST_ORDER_PREFIX = "storefront:tracking-order:latest:";
const MAX_CACHE_AGE_MS = 30 * 60 * 1000;
const MAX_ORDER_CACHE_AGE_MS = 24 * 60 * 60 * 1000;
const OPEN_SUMMARY_PREFIX = "storefront:order-summary-open:";
export const TRACKING_ORDER_UPDATED_EVENT = "storefront-tracking-order-updated";


export type CachedTrackingSnapshot = {
  token: string;
  tenant?: string | null;
  payload: Record<string, unknown>;
  createdAt: number;
};

function normalizeToken(token: string | null | undefined) {
  const normalized = String(token || "").trim();
  return normalized || null;
}

function isBrowser() {
  return typeof window !== "undefined";
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

function isFresh(createdAt: number) {
  return Date.now() - createdAt <= MAX_CACHE_AGE_MS;
}

function parseCachedOrder(rawValue: string | null): CachedTrackingOrder | null {
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as CachedTrackingOrder;
    const token = normalizeToken(parsed?.token);
    const createdAt = Number(parsed?.createdAt);

    if (!token || !Number.isFinite(createdAt) || Date.now() - createdAt > MAX_ORDER_CACHE_AGE_MS) {
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

function parseCachedSnapshot(rawValue: string | null): CachedTrackingSnapshot | null {
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as CachedTrackingSnapshot;
    const token = normalizeToken(parsed?.token);
    const createdAt = Number(parsed?.createdAt);
    const payload = parsed?.payload;

    if (!token || !Number.isFinite(createdAt) || !isFresh(createdAt) || !payload || typeof payload !== "object" || Array.isArray(payload)) {
      return null;
    }

    return {
      ...parsed,
      token,
      payload,
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
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(TRACKING_ORDER_UPDATED_EVENT));
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
  const order = getCachedTrackingOrder(latestToken);
  return order?.tenant === normalizedTenant ? order : null;
}

export function setOpenOrderSummary(tenant: string, token: string | null) {
  if (token) safeWrite(`${OPEN_SUMMARY_PREFIX}${tenant}`, token);
  else safeRemove(`${OPEN_SUMMARY_PREFIX}${tenant}`);
}

export function getOpenOrderSummary(tenant: string) {
  const order = getCachedTrackingOrder(safeRead(`${OPEN_SUMMARY_PREFIX}${tenant}`));
  return order?.tenant === tenant ? order : null;
}

export function cacheTrackingSnapshot(snapshot: Omit<CachedTrackingSnapshot, "createdAt">) {
  const token = normalizeToken(snapshot.token);
  if (!token || !snapshot.payload || typeof snapshot.payload !== "object" || Array.isArray(snapshot.payload)) {
    return;
  }

  const payload: CachedTrackingSnapshot = {
    ...snapshot,
    token,
    createdAt: Date.now(),
  };

  safeWrite(`${SNAPSHOT_PREFIX}${token}`, JSON.stringify(payload));
}

export function getCachedTrackingSnapshot(token: string | null | undefined) {
  const normalizedToken = normalizeToken(token);
  if (!normalizedToken) {
    return null;
  }

  const key = `${SNAPSHOT_PREFIX}${normalizedToken}`;
  const cached = parseCachedSnapshot(safeRead(key));
  if (!cached) {
    safeRemove(key);
  }
  return cached;
}
