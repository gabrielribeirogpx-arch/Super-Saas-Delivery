"use client";

export const dynamic = "force-dynamic";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/DriverLayout";
import { ActiveOrder, completeOrder, getActiveDelivery, startOrder } from "@/services/delivery";
import { useSSE } from "@/hooks/useSSE";

export default function ActiveDeliveryPage() {
  const router = useRouter();
  const [order, setOrder] = useState<ActiveOrder | null>(null);

  const loadActiveDelivery = useCallback(async () => {
    try {
      const response = await getActiveDelivery();
      setOrder(response);
      return response;
    } catch (err) {
      console.error("Active delivery loading error", err);
      setOrder(null);
      return null;
    }
  }, []);

  useEffect(() => {
    loadActiveDelivery();
  }, [loadActiveDelivery]);

  useEffect(() => {
    function handleVisibilityChange() {
      if (document.visibilityState === "visible") {
        loadActiveDelivery();
      }
    }

    function handleWindowFocus() {
      loadActiveDelivery();
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", handleWindowFocus);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", handleWindowFocus);
    };
  }, [loadActiveDelivery]);

  useSSE({
    onEvent: (eventName) => {
      if (eventName === "delivery_completed" || eventName === "delivery_assigned") {
        loadActiveDelivery();
      }
    },
  });

  async function handleStart(activeOrder: ActiveOrder) {
    if (activeOrder.destination) {
      localStorage.setItem("driver_destination", JSON.stringify(activeOrder.destination));
    }
    localStorage.setItem("driver_active_order_id", String(activeOrder.pedido_id));

    try {
      await startOrder(activeOrder.pedido_id);
      router.push("/driver/map");
    } catch (err) {
      console.error("Start delivery error", err);
    }
  }

  async function handleComplete(orderId: number | string) {
    try {
      await completeOrder(orderId);
      await loadActiveDelivery();
    } catch (err) {
      console.error("Complete delivery error", err);
    }
  }

  return (
    <DriverLayout title="Entrega ativa">
      {!order ? (
        <p className="text-sm text-slate-500">Nenhuma entrega ativa.</p>
      ) : (
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">Pedido #{order.pedido_id}</p>
          <p className="text-sm text-slate-700">Cliente: {order.cliente}</p>
          <p className="text-sm text-slate-700">Endereço: {order.endereco}</p>
          <p className="text-sm text-slate-700">Distância: {order.distancia_km ?? 0} km</p>

          <div className="grid grid-cols-2 gap-2 pt-2">
            <button className="rounded bg-blue-600 py-2 text-sm text-white" onClick={() => handleStart(order)}>
              Iniciar entrega
            </button>
            <button
              className="rounded bg-emerald-600 py-2 text-sm text-white"
              onClick={() => handleComplete(order.pedido_id)}
            >
              Entregue
            </button>
          </div>
        </div>
      )}
    </DriverLayout>
  );
}
