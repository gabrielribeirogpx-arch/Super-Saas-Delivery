"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/DriverLayout";
import OrderCard from "@/components/OrderCard";
import { acceptOrder, AvailableOrder, getAvailableOrders } from "@/services/delivery";
import { ApiError } from "@/services/api";
import { useSSE } from "@/hooks/useSSE";
import { useDriverStatus } from "@/hooks/useDriverStatus";

export default function DriverOrdersPage() {
  const router = useRouter();
  const { online, isHydrated, setOnline } = useDriverStatus();
  const [orders, setOrders] = useState<AvailableOrder[]>([]);
  const [isInitialLoadComplete, setIsInitialLoadComplete] = useState(false);
  const [acceptingOrderId, setAcceptingOrderId] = useState<number | string | null>(null);
  const [acceptErrorMessage, setAcceptErrorMessage] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    if (!online) {
      setOrders([]);
      return;
    }

    try {
      const response = await getAvailableOrders();
      console.debug("[driver/orders] available orders response", response);
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
    setAcceptErrorMessage(null);
    setAcceptingOrderId(orderId);

    try {
      if (!online) {
        await setOnline();
      }

      await acceptOrder(orderId);
      setOrders((currentOrders) => currentOrders.filter((order) => order.pedido_id !== orderId));
      router.push("/driver/delivery");
    } catch (err) {
      console.error("Order accept error", err);
      if (err instanceof ApiError && err.response?.status === 409) {
        setAcceptErrorMessage("Não foi possível aceitar o pedido. Verifique se você está online e tente novamente.");
      } else {
        setAcceptErrorMessage("Falha ao aceitar o pedido. Tente novamente em instantes.");
      }
    } finally {
      setAcceptingOrderId(null);
    }
  }

  return (
    <DriverLayout title="Pedidos disponíveis">
      <div className="space-y-3">
        {!online ? <p className="text-sm text-slate-500">Fique online para receber pedidos.</p> : null}
        {acceptErrorMessage ? <p className="text-sm text-red-600">{acceptErrorMessage}</p> : null}
        {orders.map((order) => (
          <OrderCard
            key={order.pedido_id}
            order={order}
            actionLabel={acceptingOrderId === order.pedido_id ? "Aceitando..." : "Aceitar entrega"}
            onAction={() => handleAccept(order.pedido_id)}
          />
        ))}
        {online && orders.length === 0 ? <p className="text-sm text-slate-500">Sem pedidos no momento.</p> : null}
      </div>
    </DriverLayout>
  );
}
