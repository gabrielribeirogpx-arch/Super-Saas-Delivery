"use client";

import { useEffect, useState } from "react";
import { getDriverState } from "@/services/delivery";

export const dynamic = "force-dynamic";

type DebugState = {
  loading: boolean;
  error: string | null;
  status: number | null;
  ok: boolean | null;
  headers: Record<string, string>;
  rawBody: string;
  parsedBody: unknown;
};

export default function DebugDeliveryPage() {
  const [data, setData] = useState<DebugState>({
    loading: true,
    error: null,
    status: null,
    ok: null,
    headers: {},
    rawBody: "",
    parsedBody: null,
  });

  useEffect(() => {
    async function load() {
      try {
        const response = await getDriverState();
        const rawBody = await response.text();

        let parsedBody: unknown = null;
        try {
          parsedBody = rawBody ? JSON.parse(rawBody) : null;
        } catch {
          parsedBody = { parseError: "Response is not valid JSON." };
        }

        setData({
          loading: false,
          error: null,
          status: response.status,
          ok: response.ok,
          headers: Object.fromEntries(response.headers.entries()),
          rawBody,
          parsedBody,
        });
      } catch (error) {
        setData((current) => ({
          ...current,
          loading: false,
          error: error instanceof Error ? error.message : "Unknown error",
        }));
      }
    }

    load();
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h1>Delivery Debug</h1>

      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
