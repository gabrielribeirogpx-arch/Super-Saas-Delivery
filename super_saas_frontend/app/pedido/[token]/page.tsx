"use client";

import { useEffect, useMemo, useState } from "react";

import { buildStorefrontApiUrl, buildStorefrontWebSocketUrl } from "@/lib/storefrontApi";

type TrackingItem = {
  name: string;
  quantity: number;
};

type TrackingPayload = {
  order_number: number;
  status: string;
  status_step: number;
  payment_method: string | null;
  total: number;
  items: TrackingItem[];
  store_name: string | null;
  store_logo_url: string | null;
  primary_color: string | null;
};

type TrackingRealtimePayload = {
  status?: string;
  status_raw?: string;
  status_step?: number;
};

const steps = ["Aguardando cozinha", "Em preparo", "Pronto", "Saiu para entrega", "Entregue"];

export default function PublicOrderTrackingPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<TrackingPayload | null>(null);
  const [notFound, setNotFound] = useState(false);

  const color = useMemo(() => data?.primary_color || "#22c55e", [data?.primary_color]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    let socket: WebSocket | null = null;

    const applyRealtimeStatus = (payload: TrackingRealtimePayload) => {
      const nextStatus = String(payload.status || payload.status_raw || "").trim();
      const nextStatusStep = Number(payload.status_step || 0);

      if (!nextStatus && !nextStatusStep) {
        return;
      }

      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          status: nextStatus || prev.status,
          status_step: nextStatusStep || prev.status_step,
        };
      });
    };

    const fetchTracking = async () => {
      try {
        const response = await fetch(buildStorefrontApiUrl(`/public/order/${params.token}`), {
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache",
            Pragma: "no-cache",
          },
        });
        if (response.status === 404) {
          setNotFound(true);
          return;
        }
        if (!response.ok) return;
        const payload = await response.json();
        setData(payload);
        setNotFound(false);
      } catch {
        // silencioso
      }
    };

    fetchTracking();

    const websocketUrl = buildStorefrontWebSocketUrl(`/ws/public/tracking/${params.token}`);
    if (websocketUrl) {
      socket = new WebSocket(websocketUrl);
      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as TrackingRealtimePayload;
          applyRealtimeStatus(parsed);
        } catch {
          // silencioso
        }
      };
    }

    interval = setInterval(fetchTracking, 15000);

    return () => {
      if (interval) clearInterval(interval);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [params.token]);

  if (notFound) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-[430px] rounded-2xl border border-slate-200 bg-white p-6 text-center">Pedido não encontrado</div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-[430px] space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="text-center">
          {data?.store_logo_url ? <img src={data.store_logo_url} alt="Logo" className="mx-auto mb-2 h-12 w-12 rounded-full object-cover" /> : null}
          <p className="text-sm text-slate-500">{data?.store_name || "Restaurante"}</p>
          <h1 className="text-[28px] italic" style={{ fontFamily: "var(--font-display)" }}>
            Pedido #{data?.order_number || "--"}
          </h1>
        </div>

        <div className="space-y-2">
          {steps.map((label, index) => {
            const done = (data?.status_step || 1) >= index + 1;
            return (
              <div key={label} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block h-3 w-3 rounded-full border ${done ? "border-transparent" : "border-slate-300"}`}
                    style={{ backgroundColor: done ? color : "transparent" }}
                  />
                  <span>{label}</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="rounded-xl border border-slate-200 p-4">
          <p className="mb-2 text-sm font-semibold">Resumo do pedido</p>
          <div className="space-y-1 text-sm">
            {data?.items?.map((item) => (
              <div key={`${item.name}-${item.quantity}`} className="flex justify-between">
                <span>{item.quantity}x {item.name}</span>
              </div>
            ))}
          </div>
          <div className="my-3 h-px bg-slate-200" />
          <div className="flex justify-between text-sm"><span>Total</span><span>R$ {Number(data?.total || 0).toFixed(2)}</span></div>
          <div className="mt-1 flex justify-between text-sm"><span>Pagamento</span><span>{String(data?.payment_method || "-").toUpperCase()}</span></div>
        </div>

        {data && ["delivered", "entregue"].includes(String(data.status || "").toLowerCase()) ? (
          <p className="text-center text-sm">Seu pedido foi entregue! Bom apetite 🍽️</p>
        ) : (
          <p className="text-center text-[11px] text-slate-500">Atualiza automaticamente em tempo real</p>
        )}
      </div>
    </main>
  );
}
