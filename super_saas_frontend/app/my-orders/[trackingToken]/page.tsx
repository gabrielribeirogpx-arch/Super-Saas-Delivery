"use client";
import { useEffect, useState } from "react";
import { buildStorefrontEventStreamUrl, storefrontFetch } from "@/lib/storefrontApi";
type Tracking = { order_number?: number; daily_order_number?: number; status?: string; status_label?: string; items?: Array<{ name?: string; quantity?: number; total_cents?: number }>; total_cents?: number; delivery_address?: string | Record<string,string>; driver_location?: { lat: number; lng: number; updated_at?: string }; last_update?: string; updated_at?: string; completed?: boolean };
export default function OrderTrackingPage({ params }: { params: { trackingToken: string } }) {
  const token = params.trackingToken;
  const [data, setData] = useState<Tracking | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let es: EventSource | null = null;
    storefrontFetch(`/api/public/order/${token}`).then(async (r) => { if (!r.ok) throw new Error("Tracking inválido ou expirado"); setData(await r.json()); }).catch((e) => setError(e.message));
    try {
      es = new EventSource(buildStorefrontEventStreamUrl(`/api/public/sse/${token}`));
      es.addEventListener("tracking_update", (event) => setData((prev) => ({ ...(prev || {}), ...JSON.parse((event as MessageEvent).data) })));
      es.onerror = () => es?.close();
    } catch {}
    return () => es?.close();
  }, [token]);
  if (error) return <main className="mx-auto max-w-md p-4 text-red-600">{error}</main>;
  if (!data) return <main className="mx-auto max-w-md p-4 text-slate-500">Carregando rastreamento...</main>;
  const number = data.daily_order_number || data.order_number;
  const updated = data.last_update || data.updated_at || data.driver_location?.updated_at;
  return <main className="mx-auto min-h-screen max-w-md bg-slate-50 p-4 pb-24"><h1 className="text-2xl font-bold">Pedido {number ? `#${number}` : ""}</h1><section className="mt-4 rounded-2xl bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Status</p><p className="text-lg font-semibold">{data.status_label || data.status || "Em acompanhamento"}</p><p className="mt-2 text-xs text-slate-500">Última atualização: {updated ? new Date(updated).toLocaleString("pt-BR") : "aguardando"}</p>{data.completed ? <p className="mt-2 text-emerald-700">Entrega concluída.</p> : null}</section><section className="mt-4 rounded-2xl bg-white p-4 shadow-sm"><h2 className="font-semibold">Itens</h2>{data.items?.length ? data.items.map((item, i) => <p className="mt-2 text-sm" key={i}>{item.quantity || 1}× {item.name}</p>) : <p className="mt-2 text-sm text-slate-500">Itens disponíveis no resumo público quando retornados pela API.</p>}<p className="mt-3 font-semibold">Total: {typeof data.total_cents === "number" ? (data.total_cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "—"}</p></section><section className="mt-4 rounded-2xl bg-white p-4 shadow-sm"><h2 className="font-semibold">Entrega</h2><p className="mt-2 text-sm text-slate-600">{typeof data.delivery_address === "string" ? data.delivery_address : "Endereço resumido protegido"}</p>{data.driver_location ? <div className="mt-3 rounded-xl bg-slate-100 p-3 text-sm">Entregador em tempo real: {data.driver_location.lat.toFixed(5)}, {data.driver_location.lng.toFixed(5)}</div> : <p className="mt-2 text-sm text-slate-500">Aguardando localização do entregador.</p>}</section></main>;
}
