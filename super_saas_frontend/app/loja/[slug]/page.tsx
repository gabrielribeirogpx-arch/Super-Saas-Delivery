"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";

import { StorefrontMenuContent } from "@/components/storefront/StorefrontMenuContent";
import { PublicMenuResponse } from "@/components/storefront/types";
import { baseUrl } from "@/lib/api";

export default function PublicStorePage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const searchParams = useSearchParams();
  const isPreview = searchParams.get("preview") === "1";

  const menuQuery = useQuery({
    queryKey: ["public-menu", slug],
    queryFn: async () => {
      const response = await fetch(`${baseUrl}/public/menu`, {
        credentials: "include",
      });
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

  return <StorefrontMenuContent menu={menuQuery.data} isPreview={isPreview} enableCart />;
}
