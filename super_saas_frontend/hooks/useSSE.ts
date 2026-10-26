"use client";

import { useEffect } from "react";

type SSEEventName =
  | "new_delivery"
  | "delivery_assigned"
  | "driver_location"
  | "delivery_completed";

type UseSSEOptions = {
  enabled?: boolean;
  onEvent?: (event: SSEEventName, data: unknown) => void;
};

const EVENTS: SSEEventName[] = [
  "new_delivery",
  "delivery_assigned",
  "driver_location",
  "delivery_completed",
];

function resolveSseBaseUrl() {
  const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL || "";

  if (!rawBaseUrl) {
    return "";
  }

  try {
    const parsed = new URL(rawBaseUrl);
    const normalizedPath = parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/$/, "");
    return `${parsed.origin}${normalizedPath}`;
  } catch {
    return rawBaseUrl.replace(/\/$/, "");
  }
}

export function useSSE({ enabled = true, onEvent }: UseSSEOptions = {}) {
  useEffect(() => {
    if (!enabled) {
      return;
    }

    const tenantId = localStorage.getItem("tenant_id");

    if (!tenantId) {
      console.warn("Tenant ID missing for SSE connection");
      return;
    }

    const sseBaseUrl = resolveSseBaseUrl();
    const eventSource = new EventSource(
      `${sseBaseUrl}/sse/delivery/status?tenant=${tenantId}`,
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
  }, [enabled, onEvent]);
}
