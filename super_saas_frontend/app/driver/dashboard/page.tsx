"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/driver/DriverLayout";
import OrderCard from "@/components/driver/OrderCard";
import { acceptOrder, getDriverState, DriverState } from "@/services/driverApi";

export default function DriverDashboardPage() {
  const router = useRouter();
  const [state, setState] = useState<DriverState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const redirectedRef = useRef(false);

  async function refresh() {
    try {
      setError(null);
      const data = await getDriverState();
      setState(data);
      if (!redirectedRef.current && data.active_delivery) {
        redirectedRef.current = true;
        router.replace(`/driver/delivery/${data.active_delivery.id}`);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load state");
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, []);

  return (
    <DriverLayout title="Available Orders">
      {error && <p className="mb-2 rounded bg-red-50 p-2 text-sm text-red-600">{error}</p>}
      {state?.available_orders?.length ? state.available_orders.map((order) => (
        <OrderCard key={order.id} order={order} onAccept={async () => {
          await acceptOrder(order.id);
          router.push(`/driver/delivery/${order.id}`);
        }} />
      )) : <p className="text-sm text-gray-600">No ready orders.</p>}
    </DriverLayout>
  );
}
