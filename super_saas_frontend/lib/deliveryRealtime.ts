const RECONNECT_DELAYS_MS = [3000, 5000, 10000] as const;

function getReconnectDelay(attempt: number) {
  return RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)];
}

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
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  let usingSSE = false;
  let isActive = true;
  let reconnectAttempt = 0;

  const notifyMode = (mode: DeliveryMode) => {
    onModeChange?.(mode);
  };

  const clearReconnectTimeout = () => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
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

  const scheduleReconnect = () => {
    if (!isActive || source || reconnectTimeout) {
      return;
    }

    const delay = getReconnectDelay(reconnectAttempt);
    reconnectAttempt = Math.min(reconnectAttempt + 1, RECONNECT_DELAYS_MS.length - 1);

    reconnectTimeout = setTimeout(() => {
      reconnectTimeout = null;
      connectSSE();
    }, delay);
  };

  const handleDisconnect = () => {
    usingSSE = false;
    stopSSE();
    scheduleReconnect();
  };

  const connectSSE = () => {
    if (!isActive || source) {
      return;
    }

    clearReconnectTimeout();

    try {
      source = startSSE(
        tenantId,
        orderId,
        (data) => publishMessage(data),
        () => {
          handleDisconnect();
        },
      );
    } catch (error) {
      logger.error("[deliveryRealtime] Unable to start SSE", error);
      handleDisconnect();
      return;
    }

    source.onopen = () => {
      usingSSE = true;
      reconnectAttempt = 0;
      notifyMode("realtime");
    };
  };

  connectSSE();

  return () => {
    isActive = false;
    usingSSE = false;
    clearReconnectTimeout();
    stopSSE();
  };
}
