"use client";

import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";

export default function OrdersPage({ params }: { params: { slug: string } }) {
  return (
    <main className="p-4 pb-24">
      <h1 className="mb-4 text-xl font-semibold">Orders</h1>
      <p className="text-sm text-slate-500">Seu histórico de pedidos ficará disponível aqui assim que existir um endpoint público para consulta.</p>
      <CustomerBottomNav slug={params.slug} />
    </main>
  );
}
