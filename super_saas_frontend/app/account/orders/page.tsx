"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { customerAccountUrl, customerMe, customerOrders, customerTenant } from "@/lib/customerAuth";
import { cacheTrackingOrder, setOpenOrderSummary } from "@/lib/orderTrackingCache";
import { formatCurrencyFromCents } from "@/lib/currency";
import { normalizeTrackingStatus, TRACKING_STEPS } from "@/lib/orderTrackingStatus";
import { LoadingExperience } from "@/components/ui/loading-experience";
type Customer = { loyalty?: { enabled: boolean; available_points: number; lifetime_points: number } };
type HistoryOrder = { order_number: number; tracking_token: string | null; status: string; total_cents: number; payment_method: string; delivery_type: string; created_at: string };
export default function Orders() {
  const [me, setMe] = useState<Customer | null>(null);
  const [orders, setOrders] = useState<HistoryOrder[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const me = await customerMe();
        if (!active) return;
        if (!me) { router.replace(customerAccountUrl("/account/login")); return; }
        setMe(me);
        const rows = await customerOrders();
        if (active) setOrders(rows);
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Não foi possível carregar seus pedidos"); }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [router]);
  return <main className="mx-auto min-h-screen max-w-md p-6 pb-24">
    <h1 className="text-2xl font-black">Meus pedidos</h1>
    {me?.loyalty?.enabled && <section className="mt-4 flex items-center justify-between rounded-2xl bg-slate-950 p-4 text-white" aria-label="Saldo de pontos">
      <div><p className="text-xs text-white/60">Saldo de pontos</p><p className="text-xl font-black">{me.loyalty.available_points.toLocaleString("pt-BR")}</p></div>
      <p className="max-w-32 text-right text-xs text-white/60">{me.loyalty.lifetime_points.toLocaleString("pt-BR")} acumulados no total</p>
    </section>}
    {loading && <LoadingExperience variant="storefront" label="Buscando seus pedidos" compact />}
    {error && <p role="alert" className="mt-4 text-red-600">{error}</p>}
    {!loading && !error && orders.length === 0 && <p className="mt-4 text-sm text-slate-600">Você ainda não fez nenhum pedido nesta loja.</p>}
    <div className="mt-4 space-y-3">{orders.map((order, index) => <button key={order.tracking_token || index} disabled={!order.tracking_token} className="block w-full rounded-2xl border p-4 text-left transition enabled:hover:border-slate-400 disabled:cursor-default" onClick={() => {
      if (!order.tracking_token) return;
      const tenant = customerTenant();
      cacheTrackingOrder({ token: order.tracking_token, tenant, orderNumber: order.order_number, totalCents: order.total_cents, paymentMethod: order.payment_method, deliveryType: order.delivery_type, status: order.status });
      setOpenOrderSummary(tenant, order.tracking_token);
      router.push(`/loja/${encodeURIComponent(tenant)}`);
    }}><div className="flex items-start justify-between gap-3"><div><b>Pedido #{order.order_number}</b><p className="mt-1 text-sm text-slate-600">{TRACKING_STEPS.find(step => step.key === normalizeTrackingStatus(order.status))?.label || "Pedido cancelado"}</p></div><b>{formatCurrencyFromCents(order.total_cents)}</b></div><div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500"><span>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(order.created_at))}</span><span>{order.delivery_type === "delivery" ? "Entrega" : "Retirada"}</span><span>{order.payment_method || "Pagamento não informado"}</span></div>{order.tracking_token && <p className="mt-3 text-xs font-semibold text-slate-700">Ver detalhes e rastreamento →</p>}</button>)}</div>
  </main>;
}
