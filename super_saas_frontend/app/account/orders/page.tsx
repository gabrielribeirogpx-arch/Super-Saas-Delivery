"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { customerAccountUrl, customerMe, customerOrders, customerTenant } from "@/lib/customerAuth";
import { cacheTrackingOrder, setOpenOrderSummary } from "@/lib/orderTrackingCache";
import { formatCurrencyFromCents } from "@/lib/currency";
import { normalizeTrackingStatus, TRACKING_STEPS } from "@/lib/orderTrackingStatus";
import { LoadingExperience } from "@/components/ui/loading-experience";
type HistoryOrder = { order_number: number; tracking_token: string | null; status: string; total_cents: number; payment_method: string; delivery_type: string };
export default function Orders() {
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
        const rows = await customerOrders();
        if (active) setOrders(rows);
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Não foi possível carregar seus pedidos"); }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [router]);
  return <main className="mx-auto min-h-screen max-w-md p-6 pb-24">
    <h1 className="text-2xl font-black">Meus pedidos</h1>
    {loading && <LoadingExperience variant="storefront" label="Buscando seus pedidos" compact />}
    {error && <p role="alert" className="mt-4 text-red-600">{error}</p>}
    {!loading && !error && orders.length === 0 && <p className="mt-4 text-sm text-slate-600">Nenhum pedido encontrado para seu telefone nesta loja.</p>}
    <div className="mt-4 space-y-3">{orders.map((order, index) => <button key={order.tracking_token || index} disabled={!order.tracking_token} className="block w-full rounded-xl border p-4 text-left" onClick={() => {
      if (!order.tracking_token) return;
      const tenant = customerTenant();
      cacheTrackingOrder({ token: order.tracking_token, tenant, orderNumber: order.order_number, totalCents: order.total_cents, paymentMethod: order.payment_method, deliveryType: order.delivery_type, status: order.status });
      setOpenOrderSummary(tenant, order.tracking_token);
      router.push(`/loja/${encodeURIComponent(tenant)}`);
    }}><b>Pedido #{order.order_number}</b><p className="text-sm">{TRACKING_STEPS.find(step => step.key === normalizeTrackingStatus(order.status))?.label || "Pedido cancelado"}</p><p>{formatCurrencyFromCents(order.total_cents)}</p></button>)}</div>
  </main>;
}
