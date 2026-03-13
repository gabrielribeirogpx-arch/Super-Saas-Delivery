"use client";

import { useEffect, useState } from "react";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
import { loadCustomerSession } from "@/components/storefront/customerSession";

type Order = { id: number; order_number?: number | null; date?: string | null; items: string[]; total: number };

export default function OrdersPage({ params }: { params: { slug: string } }) {
  const [orders, setOrders] = useState<Order[]>([]);

  useEffect(() => {
    const session = loadCustomerSession(params.slug);
    if (!session?.customerId) return;
    fetch(`/api/store/customer-orders?customer_id=${session.customerId}`, { credentials: "include" })
      .then((res) => res.json())
      .then(setOrders)
      .catch(() => setOrders([]));
  }, [params.slug]);

  return (
    <main className="p-4 pb-24">
      <h1 className="mb-4 text-xl font-semibold">Orders</h1>
      {orders.map((order) => (
        <article key={order.id} className="mb-3 rounded border p-3">
          <p className="font-medium">#{order.order_number ?? order.id}</p>
          <p className="text-sm text-slate-500">{order.date ? new Date(order.date).toLocaleString() : "-"}</p>
          <p className="text-sm">{order.items.join(", ")}</p>
          <p className="font-semibold">R$ {(order.total / 100).toFixed(2)}</p>
          <button className="mt-2 rounded bg-black px-3 py-1 text-sm text-white">Reorder</button>
        </article>
      ))}
      <CustomerBottomNav slug={params.slug} />
    </main>
  );
}
