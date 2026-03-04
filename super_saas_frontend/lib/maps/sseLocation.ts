export interface LocationEventPayload {
  lat: number;
  lng: number;
  heading?: number;
  status?: string;
  timestamp?: string;
}

export interface DeliveryStatusPayload {
  delivery_user_id: number;
  lat?: number;
  lng?: number;
  status?: string;
  updated_at?: string;
}

interface ListenLocationOptions {
  apiBase: string;
  orderId: number;
  onLocation: (payload: LocationEventPayload) => void;
}

interface ListenStatusOptions {
  apiBase: string;
  tenantId: number;
  onStatus: (payload: DeliveryStatusPayload) => void;
}

function normalizePayload(payload: unknown): LocationEventPayload | null {
  if (!payload || typeof payload !== "object") return null;
  const source = payload as Record<string, unknown>;
  const lat = Number(source.lat);
  const lng = Number(source.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;

  const headingRaw = Number(source.heading);
  return {
    lat,
    lng,
    heading: Number.isFinite(headingRaw) ? headingRaw : undefined,
    status: typeof source.status === "string" ? source.status : undefined,
    timestamp: typeof source.timestamp === "string" ? source.timestamp : undefined,
  };
}

function parseJson(data: string): unknown {
  return JSON.parse(data) as unknown;
}

export function listenOrderLocation({ apiBase, orderId, onLocation }: ListenLocationOptions): () => void {
  const url = `${apiBase}/sse/delivery/location?order_id=${orderId}`;
  const eventSource = new EventSource(url, { withCredentials: true });

  eventSource.onmessage = (event) => {
    try {
      const normalized = normalizePayload(parseJson(event.data));
      if (normalized) onLocation(normalized);
    } catch {
      // no-op
    }
  };

  return () => eventSource.close();
}

export function listenTenantDeliveryStatus({ apiBase, tenantId, onStatus }: ListenStatusOptions): () => void {
  const url = `${apiBase}/sse/delivery/status?tenant_id=${tenantId}`;
  const eventSource = new EventSource(url, { withCredentials: true });

  eventSource.onmessage = (event) => {
    try {
      const payload = parseJson(event.data) as DeliveryStatusPayload;
      onStatus(payload);
    } catch {
      // no-op
    }
  };

  return () => eventSource.close();
}
