"use client";

import { useEffect, useState } from "react";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
import { loadCustomerSession } from "@/components/storefront/customerSession";

export default function DiscountsPage({ params }: { params: { slug: string } }) {
  const [data, setData] = useState<{ is_vip: boolean; total_orders: number; total_spent: number } | null>(null);

  useEffect(() => {
    const session = loadCustomerSession(params.slug);
    if (!session?.customerId) return;
    fetch(`/api/store/customer-discounts?customer_id=${session.customerId}`, { credentials: "include" })
      .then((res) => res.json())
      .then(setData);
  }, [params.slug]);

  return (
    <main className="p-4 pb-24">
      <h1 className="mb-4 text-xl font-semibold">Discounts</h1>
      <p className="text-sm">VIP: {data?.is_vip ? "Yes" : "No"}</p>
      <p className="text-sm">Orders: {data?.total_orders ?? 0}</p>
      <p className="text-sm">Spent: R$ {((data?.total_spent ?? 0) / 100).toFixed(2)}</p>
      <CustomerBottomNav slug={params.slug} />
    </main>
  );
}
