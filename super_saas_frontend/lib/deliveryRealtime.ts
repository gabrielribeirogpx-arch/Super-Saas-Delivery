const DEFAULT_RECONNECT_INTERVAL_MS = 30000;

const RAW_API = process.env.NEXT_PUBLIC_API_URL;

function resolveApiBasePath() {
  if (!RAW_API) {
    return "";
  }

  try {
    const parsed = new URL(RAW_API);
    return parsed.pathname.replace(/\/$/, "");
  } catch {
    return RAW_API.replace(/\/$/, "");
  }
}

const API_BASE = resolveApiBasePath();

type DeliveryMode = "realtime";

interface SubscribeDeliveryOptions {
  tenantId: number;
  orderId?: number | null;
  onMessage: (data: unknown) => void;
  onModeChange?: (mode: DeliveryMode) => void;
  logger?: Pick<typeof console, "error" | "warn">;
}

const startSSE = (tenantId: number, orderId: number | null, onMessage: (data: unknown) => void, onError: () => void) => {
  const url =
    orderId === null
      ? `${API_BASE}/sse/delivery/status?tenant=${tenantId}`
      : `${API_BASE}/sse/delivery/${orderId}?tenant=${tenantId}`;

  console.log("Connecting SSE to:", url);

  const eventSource = new EventSource(url, { withCredentials: true });

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as unknown;
      onMessage(data);
    } catch (error) {
      console.warn("[deliveryRealtime] Invalid SSE payload", error);
    }
  };

  eventSource.onerror = (err) => {
    console.error("SSE error:", err);
    eventSource.close();
    onError();
  };

  return eventSource;
};

export function subscribeDelivery({
  tenantId,
  orderId = null,
  onMessage,
  onModeChange,
  logger = console,
}: SubscribeDeliveryOptions) {
  let source: EventSource | undefined;
  let reconnectInterval: ReturnType<typeof setInterval> | null = null;
  let usingSSE = false;
  let isActive = true;

  const notifyMode = (mode: DeliveryMode) => {
    onModeChange?.(mode);
  };

  const stopSSE = () => {
    if (source) {
      source.close();
      source = undefined;
    }
  };

  const publishMessage = (data: unknown) => {
    if (!data) {
      return;
    }

    if (Array.isArray(data)) {
      data.forEach((item) => onMessage(item));
      return;
    }

    onMessage(data);
  };

  const connectSSE = () => {
    if (!isActive || source) {
      return;
    }

    try {
      source = startSSE(
        tenantId,
        orderId,
        (data) => publishMessage(data),
        () => {
          usingSSE = false;
          source = undefined;
        },
      );
    } catch (error) {
      logger.error("[deliveryRealtime] Unable to start SSE", error);
      usingSSE = false;
      source = undefined;
      return;
    }

    source.onopen = () => {
      usingSSE = true;
      notifyMode("realtime");
    };
  };

  const autoReconnectSSE = () => {
    if (reconnectInterval) {
      return;
    }

    reconnectInterval = setInterval(() => {
      if (!usingSSE) {
        connectSSE();
      }
    }, DEFAULT_RECONNECT_INTERVAL_MS);
  };

  connectSSE();
  autoReconnectSSE();

  return () => {
    isActive = false;
    usingSSE = false;
    stopSSE();

    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }
  };
}
