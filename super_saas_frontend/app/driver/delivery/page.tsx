"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/DriverLayout";
import OrderCard from "@/components/OrderCard";
import { completeOrder, getActiveOrders, startOrder, ActiveOrder } from "@/services/delivery";
import { useSSE } from "@/hooks/useSSE";

export default function ActiveDeliveryPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<ActiveOrder[]>([]);

  const loadOrders = useCallback(async () => {
    try {
      const response = await getActiveOrders();
      console.log("active delivery response", response);
      setOrders(response);
      return response;
    } catch (err) {
      console.error("Active deliveries loading error", err);
      setOrders([]);
      return [];
    }
  }, []);

  useEffect(() => {
    let retries = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    async function initialLoad() {
      const initialOrders = await loadOrders();

      if (initialOrders.length === 0) {
        const scheduleRetry = () => {
          if (retries >= 3) {
            return;
          }

          retryTimer = setTimeout(async () => {
            retries += 1;
            const retriedOrders = await loadOrders();

            if (retriedOrders.length === 0) {
              scheduleRetry();
            }
          }, 1200);
        };

        scheduleRetry();
      }
    }

    initialLoad();

    function handleVisibilityChange() {
      if (document.visibilityState === "visible") {
        loadOrders();
      }
    }

    function handleWindowFocus() {
      loadOrders();
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", handleWindowFocus);

    return () => {
      if (retryTimer) {
        clearTimeout(retryTimer);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", handleWindowFocus);
    };
  }, [loadOrders]);

  useSSE({
    onEvent: (eventName) => {
      if (eventName === "delivery_completed" || eventName === "delivery_assigned") {
        loadOrders();
      }
    },
  });

  async function handleStart(order: ActiveOrder) {
    if (order.destination) {
      localStorage.setItem("driver_destination", JSON.stringify(order.destination));
    }
    localStorage.setItem("driver_active_order_id", String(order.pedido_id));

    try {
      await startOrder(order.pedido_id);
      router.push("/driver/map");
    } catch (err) {
      console.error("Start delivery error", err);
    }
  }

  async function handleComplete(orderId: number | string) {
    try {
      await completeOrder(orderId);
      await loadOrders();
    } catch (err) {
      console.error("Complete delivery error", err);
    }
  }

  return (
    <DriverLayout title="Entrega ativa">
      <div className="space-y-3">
        {orders.map((order) => (
          <div key={order.pedido_id} className="space-y-2">
            <OrderCard order={order} />
            <div className="grid grid-cols-2 gap-2">
              <button
                className="rounded bg-blue-600 py-2 text-sm text-white"
                onClick={() => handleStart(order)}
              >
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
        ))}
        {orders.length === 0 ? <p className="text-sm text-slate-500">Nenhuma entrega ativa.</p> : null}
      </div>
    </DriverLayout>
  );
}
