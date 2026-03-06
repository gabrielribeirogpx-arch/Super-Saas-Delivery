"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/DriverLayout";
import OrderCard from "@/components/OrderCard";
import { acceptOrder, AvailableOrder, getAvailableOrders } from "@/services/delivery";
import { useSSE } from "@/hooks/useSSE";
import { useDriverStatus } from "@/hooks/useDriverStatus";

export default function DriverOrdersPage() {
  const router = useRouter();
  const { online, isHydrated } = useDriverStatus();
  const [orders, setOrders] = useState<AvailableOrder[]>([]);
  const [isInitialLoadComplete, setIsInitialLoadComplete] = useState(false);

  const loadOrders = useCallback(async () => {
    if (!online) {
      setOrders([]);
      return;
    }

    try {
      const response = await getAvailableOrders();
      setOrders(response);
    } catch (err) {
      console.error("Orders loading error", err);
      setOrders([]);
    }
  }, [online]);

  useEffect(() => {
    let isMounted = true;

    async function initializeOrders() {
      try {
        await loadOrders();
      } finally {
        if (isMounted) {
          setIsInitialLoadComplete(true);
        }
      }
    }

    if (isHydrated) {
      initializeOrders();
    }

    return () => {
      isMounted = false;
    };
  }, [isHydrated, loadOrders]);

  useSSE({
    enabled: isInitialLoadComplete && online,
    onEvent: (eventName) => {
      if (eventName === "new_delivery" || eventName === "delivery_assigned") {
        loadOrders();
      }
    },
  });

  async function handleAccept(orderId: number | string) {
    try {
      await acceptOrder(orderId);
      router.push("/driver/delivery");
    } catch (err) {
      console.error("Order accept error", err);
    }
  }

  return (
    <DriverLayout title="Pedidos disponíveis">
      <div className="space-y-3">
        {!online ? <p className="text-sm text-slate-500">Fique online para receber pedidos.</p> : null}
        {orders.map((order) => (
          <OrderCard
            key={order.pedido_id}
            order={order}
            actionLabel="Aceitar entrega"
            onAction={() => handleAccept(order.pedido_id)}
          />
        ))}
        {online && orders.length === 0 ? <p className="text-sm text-slate-500">Sem pedidos no momento.</p> : null}
      </div>
    </DriverLayout>
  );
}
