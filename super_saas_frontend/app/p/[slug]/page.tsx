"use client";

import { useQuery } from "@tanstack/react-query";

import { StorefrontMenuContent } from "@/components/storefront/StorefrontMenuContent";
import { fetchPublicMenuBySlug } from "@/lib/public-menu";

export default function PublicPreviewPage({ params }: { params: { slug: string } }) {
  const { slug } = params;

  const menuQuery = useQuery({
    queryKey: ["public-menu-preview", slug],
    queryFn: async () => {
      return fetchPublicMenuBySlug(slug);
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

  return <StorefrontMenuContent menu={menuQuery.data} isPreview enableCart={false} />;
}
