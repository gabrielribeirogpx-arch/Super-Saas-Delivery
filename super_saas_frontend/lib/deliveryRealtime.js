const DEFAULT_POLLING_INTERVAL_MS = 3000;
const DEFAULT_RECONNECT_INTERVAL_MS = 30000;

export function createDeliveryRealtime({ tenantId, orderId, updateMarker, logger = console }) {
  let source;
  let pollingInterval = null;
  let reconnectInterval = null;
  let usingSSE = false;
  let isActive = false;
  let pollingInFlight = false;

  const endpointSse = `/sse/delivery/${tenantId}/${orderId}`;
  const endpointPolling = `/api/delivery/${tenantId}/${orderId}/last-location`;

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

  const handleMarker = (data) => {
    if (!data) return;

    const lat = Number(data.lat);
    const lng = Number(data.lng);

    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      updateMarker(lat, lng, data.timestamp ?? null);
    }
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
        const response = await fetch(endpointPolling, { credentials: "include" });
        if (!response.ok) {
          throw new Error(`Polling request failed with status ${response.status}`);
        }

        const data = await response.json();
        handleMarker(data);
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
    };

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMarker(data);
      } catch (error) {
        logger.warn("[deliveryRealtime] Invalid SSE payload", error);
      }
    };

    source.onerror = () => {
      usingSSE = false;
      stopSSE();
      startPolling();
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

  const start = () => {
    isActive = true;
    startSSE();
    autoReconnectSSE();
  };

  const stop = () => {
    isActive = false;
    usingSSE = false;
    stopSSE();
    stopPolling();

    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }
  };

  return {
    start,
    stop,
    startSSE,
    startPolling,
    stopPolling,
    autoReconnectSSE,
    getState: () => ({ usingSSE, hasPolling: Boolean(pollingInterval) }),
  };
}
