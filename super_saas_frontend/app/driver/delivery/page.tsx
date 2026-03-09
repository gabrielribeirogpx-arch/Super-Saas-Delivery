"use client";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const revalidate = 0;

import { useEffect, useState } from "react";

type ActiveDeliveryResponse = unknown;

export default function DriverDeliveryPage() {
  const [data, setData] = useState<ActiveDeliveryResponse>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const fetchActiveDelivery = async () => {
      try {
        const response = await fetch("/api/delivery/driver/active", {
          method: "GET",
          cache: "no-store",
          headers: {
            "Cache-Control": "no-store, no-cache, must-revalidate",
            Pragma: "no-cache",
            Expires: "0",
          },
        });

        const result = await response.json();
        console.log("DELIVERY FETCH RESULT:", result);

        if (!mounted) return;

        setData(result);
        setError(response.ok ? null : `HTTP ${response.status}`);
      } catch (err) {
        console.error("DELIVERY FETCH ERROR:", err);
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Erro desconhecido");
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchActiveDelivery();
    const intervalId = setInterval(fetchActiveDelivery, 2000);

    return () => {
      mounted = false;
      clearInterval(intervalId);
    };
  }, []);

  return (
    <main className="min-h-screen p-4">
      <h1 className="mb-4 text-xl font-bold">Entrega ativa</h1>

      {loading ? <p>Carregando...</p> : null}
      {!loading && error ? <p>Erro: {error}</p> : null}
      {!loading && !error && !data ? <p>Nenhuma entrega ativa.</p> : null}

      <pre className="mt-4 overflow-x-auto rounded border bg-slate-100 p-3 text-xs">
        {JSON.stringify(data, null, 2)}
      </pre>
    </main>
  );
}
