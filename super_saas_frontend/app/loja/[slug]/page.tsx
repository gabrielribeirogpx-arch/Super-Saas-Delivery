"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StorefrontMenuContent } from "@/components/storefront/StorefrontMenuContent";
import { PublicMenuResponse } from "@/components/storefront/types";
import { storefrontFetch } from "@/lib/storefrontApi";
import { getLatestCachedTrackingOrder, type CachedTrackingOrder } from "@/lib/orderTrackingCache";

export default function PublicStorePage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [recentOrder, setRecentOrder] = useState<CachedTrackingOrder | null>(null);
  useEffect(() => {
    setRecentOrder(getLatestCachedTrackingOrder(slug));
  }, [slug]);
  const menuQuery = useQuery({
    queryKey: ["public-menu", slug],
    queryFn: async () => {
      const response = await storefrontFetch(`/public/menu?slug=${encodeURIComponent(slug)}`, {
        cache: "no-store",
        credentials: "include",
      }, slug);
      if (!response.ok) {
        throw new Error("Falha ao carregar cardápio");
      }
      return (await response.json()) as PublicMenuResponse;
    },
  });

  if (menuQuery.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (menuQuery.isError || !menuQuery.data) {
    return (
      <div className="p-6 text-sm text-red-600">
        Não foi possível carregar o cardápio.
      </div>
    );
  }

  return (
    <>
      {recentOrder && (
        <div className="mx-auto max-w-[430px] p-4">
          <a
            className="block rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-center text-sm font-semibold text-emerald-800"
            href={`/pedido/${encodeURIComponent(recentOrder.token)}?tenant=${encodeURIComponent(slug)}`}
          >
            Acompanhar pedido{recentOrder.orderNumber ? ` #${recentOrder.orderNumber}` : ""}
          </a>
        </div>
      )}
      <StorefrontMenuContent menu={menuQuery.data} enableCart />
    </>
  );
}
