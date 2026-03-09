"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/DriverLayout";
import OrderCard from "@/components/OrderCard";
import { completeOrder, getActiveDelivery, startOrder, type ActiveOrder } from "@/services/delivery";

export default function DriverDeliveryPage() {
  const router = useRouter();
  const [order, setOrder] = useState<ActiveOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);

  const loadActiveDelivery = useCallback(async () => {
    try {
      const activeOrder = await getActiveDelivery();
      setOrder(activeOrder);
      setError(null);
    } catch (err) {
      console.error("DELIVERY FETCH ERROR:", err);
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    const refresh = async () => {
      if (!mounted) return;
      await loadActiveDelivery();
    };

    refresh();
    const intervalId = setInterval(refresh, 5000);

    return () => {
      mounted = false;
      clearInterval(intervalId);
    };
  }, [loadActiveDelivery]);

  async function handleStartDelivery() {
    if (!order) return;

    setIsStarting(true);
    try {
      await startOrder(order.pedido_id);
      await loadActiveDelivery();
      router.push("/driver/map");
    } catch (err) {
      console.error("Start delivery error", err);
      setError("Não foi possível iniciar a entrega. Tente novamente.");
    } finally {
      setIsStarting(false);
    }
  }

  async function handleCompleteDelivery() {
    if (!order) return;

    setIsCompleting(true);
    try {
      await completeOrder(order.pedido_id);
      await loadActiveDelivery();
      router.push("/driver/orders");
    } catch (err) {
      console.error("Complete delivery error", err);
      setError("Não foi possível concluir a entrega. Tente novamente.");
    } finally {
      setIsCompleting(false);
    }
  }

  return (
    <DriverLayout title="Entrega ativa">
      <div className="space-y-3">
        {loading ? <p className="text-sm text-slate-500">Carregando...</p> : null}
        {!loading && error ? <p className="text-sm text-rose-600">Erro: {error}</p> : null}
        {!loading && !error && !order ? <p className="text-sm text-slate-500">Nenhuma entrega ativa.</p> : null}

        {order ? (
          <>
            <OrderCard order={order} />
            <button
              type="button"
              onClick={handleStartDelivery}
              disabled={isStarting || isCompleting}
              className="w-full rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isStarting ? "Iniciando..." : "Iniciar entrega"}
            </button>

            <button
              type="button"
              onClick={handleCompleteDelivery}
              disabled={isStarting || isCompleting}
              className="w-full rounded bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isCompleting ? "Finalizando..." : "Entregue"}
            </button>
          </>
        ) : null}
      </div>
    </DriverLayout>
  );
}
