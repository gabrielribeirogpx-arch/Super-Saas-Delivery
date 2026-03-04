"use client";

import { useEffect } from "react";
import { normalizeUrl } from "@/services/api";

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

export function useSSE({ onEvent }: UseSSEOptions = {}) {
  useEffect(() => {
    const token = localStorage.getItem("driver_token");
    const endpoint = normalizeUrl("/sse/delivery/status");
    const eventSource = new EventSource(
      token ? `${endpoint}${endpoint.includes("?") ? "&" : "?"}token=${token}` : endpoint,
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
