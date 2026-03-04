const DEFAULT_POLLING_INTERVAL_MS = 3000;
const DEFAULT_RECONNECT_INTERVAL_MS = 30000;

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

  const endpointSse =
    orderId === null ? `/sse/delivery/status?tenant_id=${tenantId}` : `/sse/delivery/${tenantId}/${orderId}`;
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

  const startSSE = () => {
    if (!isActive || source) {
      return;
    }

    source = new EventSource(endpointSse, { withCredentials: true });

    source.onopen = () => {
      usingSSE = true;
      stopPolling();
      notifyMode("realtime");
    };

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as unknown;
        publishMessage(data);
      } catch (error) {
        logger.warn("[deliveryRealtime] Invalid SSE payload", error);
      }
    };

    source.onerror = () => {
      usingSSE = false;
      stopSSE();
      startPolling();
      notifyMode("fallback");
    };
  };

  const autoReconnectSSE = () => {
    if (reconnectInterval) {
      return;
    }

    reconnectInterval = setInterval(() => {
      if (!usingSSE) {
        startSSE();
      }
    }, DEFAULT_RECONNECT_INTERVAL_MS);
  };

  startSSE();
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
