const DEFAULT_POLLING_INTERVAL_MS = 3000;
const DEFAULT_RECONNECT_INTERVAL_MS = 30000;

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "");

type DeliveryMode = "realtime" | "fallback";

type PollFallback = () => Promise<unknown>;

interface SubscribeDeliveryOptions {
  tenantId: number;
  orderId?: number | null;
  onMessage: (data: unknown) => void;
  onModeChange?: (mode: DeliveryMode) => void;
  pollFallback?: PollFallback;
  logger?: Pick<typeof console, "error" | "warn">;
}

const startSSE = (tenantId: number, orderId: number | null, onMessage: (data: unknown) => void, onError: () => void) => {
  if (!API_BASE) {
    throw new Error("[deliveryRealtime] VITE_API_URL is required to connect SSE");
  }

  const url =
    orderId === null
      ? `${API_BASE}/sse/delivery/status?tenant_id=${tenantId}`
      : `${API_BASE}/sse/delivery/${tenantId}/${orderId}`;

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
  pollFallback,
  logger = console,
}: SubscribeDeliveryOptions) {
  let source: EventSource | undefined;
  let pollingInterval: ReturnType<typeof setInterval> | null = null;
  let reconnectInterval: ReturnType<typeof setInterval> | null = null;
  let usingSSE = false;
  let isActive = true;
  let pollingInFlight = false;

  const endpointPolling = orderId === null ? null : `/api/delivery/${tenantId}/${orderId}/last-location`;

  const notifyMode = (mode: DeliveryMode) => {
    onModeChange?.(mode);
  };

  const stopPolling = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
    pollingInFlight = false;
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

  const startPolling = () => {
    if (!isActive || pollingInterval || usingSSE) {
      return;
    }

    pollingInterval = setInterval(async () => {
      if (!isActive || usingSSE) {
        stopPolling();
        return;
      }

      if (pollingInFlight) {
        return;
      }

      pollingInFlight = true;

      try {
        if (pollFallback) {
          const data = await pollFallback();
          publishMessage(data);
          return;
        }

        if (!endpointPolling) {
          return;
        }

        const response = await fetch(endpointPolling, { credentials: "include" });
        if (!response.ok) {
          throw new Error(`Polling request failed with status ${response.status}`);
        }

        const data = (await response.json()) as unknown;
        publishMessage(data);
      } catch (error) {
        logger.error("[deliveryRealtime] Polling error", error);
      } finally {
        pollingInFlight = false;
      }
    }, DEFAULT_POLLING_INTERVAL_MS);
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
          startPolling();
          notifyMode("fallback");
        },
      );
    } catch (error) {
      logger.error("[deliveryRealtime] Unable to start SSE", error);
      usingSSE = false;
      source = undefined;
      startPolling();
      notifyMode("fallback");
      return;
    }

    source.onopen = () => {
      usingSSE = true;
      stopPolling();
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
    stopPolling();

    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }
  };
}
