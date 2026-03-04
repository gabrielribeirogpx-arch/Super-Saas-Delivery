"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/DriverLayout";
import OrderCard from "@/components/OrderCard";
import { acceptOrder, AvailableOrder, getAvailableOrders } from "@/services/delivery";
import { useSSE } from "@/hooks/useSSE";

export default function DriverOrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<AvailableOrder[]>([]);

  const loadOrders = useCallback(async () => {
    try {
      const response = await getAvailableOrders();
      setOrders(response);
    } catch (err) {
      console.error("Orders loading error", err);
      setOrders([]);
    }
  }, []);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  useSSE({
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
        {orders.map((order) => (
          <OrderCard
            key={order.pedido_id}
            order={order}
            actionLabel="Aceitar entrega"
            onAction={() => handleAccept(order.pedido_id)}
          />
        ))}
        {orders.length === 0 ? <p className="text-sm text-slate-500">Sem pedidos no momento.</p> : null}
      </div>
    </DriverLayout>
  );
}
