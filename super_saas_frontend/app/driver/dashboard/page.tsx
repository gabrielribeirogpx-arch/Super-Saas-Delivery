"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/driver/DriverLayout";
import OrderCard from "@/components/driver/OrderCard";
import { acceptOrder, getDriverState, DriverState } from "@/services/driverApi";
import { driverLocationService } from "@/services/driverLocationService";
import { t } from "@/i18n/translate";

export default function DriverDashboardPage() {
  const router = useRouter();
  const [state, setState] = useState<DriverState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  async function refresh() {
    try {
      setError(null);
      const data = await getDriverState();
      setState(data);
    } catch (err: any) {
      setError(err?.message || t("failed_to_load_state"));
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 4000);
    const online = () => { setOffline(false); driverLocationService.retryLatest().catch(() => undefined); };
    const offlineHandler = () => setOffline(true);
    window.addEventListener("online", online);
    window.addEventListener("offline", offlineHandler);
    setOffline(!navigator.onLine);
    return () => { clearInterval(timer); window.removeEventListener("online", online); window.removeEventListener("offline", offlineHandler); };
  }, []);

  const assigned = useMemo(() => state?.assigned_orders || (state?.active_delivery ? [state.active_delivery] : []), [state]);
  const inProgress = assigned.filter((o) => ["OUT_FOR_DELIVERY", "IN_TRANSIT", "PICKED_UP", "ARRIVED"].includes(o.status));

  return (
    <DriverLayout title="Área do entregador">
      {offline && <p className="mb-3 rounded-xl bg-amber-100 p-3 text-sm font-semibold text-amber-800">Sem conexão. Status só é confirmado após resposta do servidor.</p>}
      {error && <p className="mb-3 rounded-xl bg-red-50 p-3 text-sm text-red-600">{error}</p>}
      <section className="mb-4 grid grid-cols-2 gap-2">
        <div className="rounded-2xl bg-emerald-50 p-3"><p className="text-xs text-emerald-700">Disponíveis</p><strong>{state?.available_orders?.length ?? 0}</strong></div>
        <div className="rounded-2xl bg-blue-50 p-3"><p className="text-xs text-blue-700">Minhas entregas</p><strong>{assigned.length}</strong></div>
        <div className="rounded-2xl bg-orange-50 p-3"><p className="text-xs text-orange-700">Em andamento</p><strong>{inProgress.length}</strong></div>
        <div className="rounded-2xl bg-slate-100 p-3"><p className="text-xs text-slate-700">Concluídas hoje</p><strong>{state?.completed_today ?? 0}</strong></div>
      </section>
      <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">Minhas entregas</h2>
      {assigned.length ? assigned.map((order) => <OrderCard key={order.id} order={order} onOpen={() => router.push(`/driver/deliveries/${order.id}`)} />) : <p className="mb-4 text-sm text-gray-600">Nenhuma entrega atribuída.</p>}
      <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">Entregas disponíveis</h2>
      {state?.available_orders?.length ? state.available_orders.map((order) => (
        <OrderCard key={order.id} order={order} onOpen={() => router.push(`/driver/deliveries/${order.id}`)} onAccept={async () => { await acceptOrder(order.id); router.push(`/driver/deliveries/${order.id}`); }} />
      )) : <p className="text-sm text-gray-600">{t("no_ready_orders")}</p>}
    </DriverLayout>
  );
}
