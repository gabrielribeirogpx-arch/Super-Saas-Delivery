"use client";

import { useEffect } from "react";

type SSEEventName =
  | "new_delivery"
  | "delivery_assigned"
  | "driver_location"
  | "delivery_completed";

type UseSSEOptions = {
  onEvent?: (event: SSEEventName, data: unknown) => void;
};

const EVENTS: SSEEventName[] = [
  "new_delivery",
  "delivery_assigned",
  "driver_location",
  "delivery_completed",
];

function resolveSseBasePath() {
  const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL || "";

  if (!rawBaseUrl) {
    return "";
  }

  try {
    const parsed = new URL(rawBaseUrl);
    return parsed.pathname.replace(/\/$/, "");
  } catch {
    return rawBaseUrl.replace(/\/$/, "");
  }
}

export function useSSE({ onEvent }: UseSSEOptions = {}) {
  useEffect(() => {
    const tenantId = localStorage.getItem("tenant_id");

    if (!tenantId) {
      console.warn("Tenant ID missing for SSE connection");
      return;
    }

    const sseBasePath = resolveSseBasePath();
    const eventSource = new EventSource(
      `${sseBasePath}/sse/delivery/status?tenant_id=${tenantId}`,
      { withCredentials: true }
    );

    EVENTS.forEach((eventName) => {
      eventSource.addEventListener(eventName, (evt) => {
        let payload: unknown = null;
        if (evt instanceof MessageEvent && evt.data) {
          try {
            payload = JSON.parse(evt.data);
          } catch {
            payload = evt.data;
          }
        }
        onEvent?.(eventName, payload);
      });
    });

    return () => eventSource.close();
  }, [onEvent]);
}
