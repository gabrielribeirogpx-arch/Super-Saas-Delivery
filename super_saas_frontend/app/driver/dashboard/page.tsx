"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import DriverLayout from "@/components/driver/DriverLayout";
import DriverAuthGuard from "@/components/driver/DriverAuthGuard";
import OrderCard from "@/components/driver/OrderCard";
import { DriverEmptyState, DriverStatCard, AlertTriangle, CheckCircle2, Clock3, PackageCheck } from "@/components/driver/DriverUI";
import { acceptOrder, getDriverState, DriverState } from "@/services/driverApi";
import { driverLocationService } from "@/services/driverLocationService";
import { hasDriverSession, redirectToDriverLogin } from "@/lib/driverAuth";
import { t } from "@/i18n/translate";

export default function DriverDashboardPage() {
  const router = useRouter();
  const [state, setState] = useState<DriverState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  async function refresh() {
    if (!hasDriverSession()) {
      redirectToDriverLogin();
      return "stop" as const;
    }

    try {
      setError(null);
      const data = await getDriverState();
      setState(data);
      return "success" as const;
    } catch (err: any) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        redirectToDriverLogin();
        return "stop" as const;
      }
      setError(err?.message || t("failed_to_load_state"));
      return "retry" as const;
    }
  }

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let consecutiveFailures = 0;

    const scheduleRefresh = (delay: number) => {
      if (stopped) return;
      timer = setTimeout(async () => {
        const shouldContinue = await refresh();
        if (shouldContinue === "stop") {
          stopped = true;
          return;
        }
        consecutiveFailures = shouldContinue === "success" ? 0 : consecutiveFailures + 1;
        scheduleRefresh(consecutiveFailures > 0 ? Math.min(30000, 4000 * 2 ** Math.min(consecutiveFailures, 3)) : 4000);
      }, delay);
    };

    void refresh().then((shouldContinue) => {
      if (shouldContinue !== "stop") scheduleRefresh(4000);
    });
    const online = () => { setOffline(false); driverLocationService.retryLatest().catch(() => undefined); };
    const offlineHandler = () => setOffline(true);
    window.addEventListener("online", online);
    window.addEventListener("offline", offlineHandler);
    setOffline(!navigator.onLine);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offlineHandler);
    };
  }, []);

  const assigned = useMemo(() => state?.assigned_orders || (state?.active_delivery ? [state.active_delivery] : []), [state]);
  const inProgress = assigned.filter((o) => ["OUT_FOR_DELIVERY", "IN_TRANSIT", "PICKED_UP", "ARRIVED"].includes(o.status));

  return (
    <DriverAuthGuard>
      <DriverLayout title="Área do entregador" name={state?.driver?.name?.split(" ")[0]} offline={offline} hasRoute={Boolean(state?.active_delivery)}>
      <section className="mb-4 rounded-3xl bg-slate-950 p-5 text-white shadow-xl shadow-slate-200">
        <p className="text-xl font-black">Olá, {state?.driver?.name?.split(" ")[0] || "entregador"}</p>
        <p className="mt-1 text-sm font-medium text-slate-300">Pronto para as entregas de hoje?</p>
      </section>
      {offline && <p className="mb-3 rounded-2xl bg-amber-50 p-3 text-sm font-bold text-amber-800 ring-1 ring-amber-200">Sem conexão. Status só é confirmado após resposta do servidor.</p>}
      {error && <p className="mb-3 rounded-2xl bg-red-50 p-3 text-sm font-bold text-red-700 ring-1 ring-red-200">{error}</p>}
      {!state && !error ? <section className="mb-5 grid grid-cols-2 gap-3">{[0,1,2,3].map((i) => <div key={i} className="h-32 animate-pulse rounded-3xl bg-white/80" />)}</section> : <section className="mb-5 grid grid-cols-2 gap-3">
        <DriverStatCard icon={<PackageCheck className="h-5 w-5" />} value={state?.available_orders?.length ?? 0} title="Disponíveis" tone="emerald" href="/driver/deliveries" />
        <DriverStatCard icon={<Clock3 className="h-5 w-5" />} value={assigned.length} title="Minhas entregas" tone="blue" href="/driver/deliveries" />
        <DriverStatCard icon={<AlertTriangle className="h-5 w-5" />} value={inProgress.length} title="Em andamento" tone="orange" href="/driver/deliveries" />
        <DriverStatCard icon={<CheckCircle2 className="h-5 w-5" />} value={state?.completed_today ?? 0} title="Concluídas hoje" tone="slate" />
      </section>}
      <h2 className="mb-2 text-sm font-black uppercase tracking-wide text-slate-500">Minhas entregas</h2>
      {assigned.length ? assigned.map((order) => <OrderCard key={order.id} order={order} onOpen={() => router.push(`/driver/deliveries/${order.id}`)} />) : <DriverEmptyState title="Nenhuma entrega em andamento" message="Quando você aceitar uma entrega, ela aparecerá aqui." />}
      <h2 className="mb-2 mt-5 text-sm font-black uppercase tracking-wide text-slate-500">Entregas disponíveis</h2>
      {state?.available_orders?.length ? state.available_orders.map((order) => (
        <OrderCard key={order.id} order={order} onOpen={() => router.push(`/driver/deliveries/${order.id}`)} onAccept={async () => { await acceptOrder(order.id); router.push(`/driver/deliveries/${order.id}`); }} />
      )) : <DriverEmptyState title="Nenhuma entrega disponível" message={t("no_ready_orders")} />}
      </DriverLayout>
    </DriverAuthGuard>
  );
}
