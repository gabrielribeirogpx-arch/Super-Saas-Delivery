"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

interface TenantResponse {
  id: number;
  slug: string;
  custom_domain: string | null;
  business_name: string;
}

interface MenuCategory {
  id: number;
  name: string;
}

interface MenuItem {
  id: number;
  category_id: number | null;
  name: string;
  active: boolean;
}

const getPublicBaseUrl = () => {
  if (typeof window === "undefined") {
    return "";
  }
  return window.location.origin;
};

export default function StorefrontPreviewPage() {
  const [tenant, setTenant] = useState<TenantResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const categoriesQuery = useQuery({
    queryKey: ["preview-menu-categories"],
    queryFn: () => api.get<MenuCategory[]>("/api/admin/menu/categories"),
  });

  const itemsQuery = useQuery({
    queryKey: ["preview-menu-items"],
    queryFn: () => api.get<MenuItem[]>("/api/admin/menu/items"),
  });

  useEffect(() => {
    const fetchTenant = async () => {
      try {
        const data = await api.get<TenantResponse>("/api/admin/tenant");
        setTenant(data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Não foi possível carregar o tenant.";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTenant();
  }, []);

  const previewUrl = useMemo(() => {
    if (!tenant?.slug) {
      return "";
    }
    const publicBaseUrl = getPublicBaseUrl();
    if (!publicBaseUrl) {
      return "";
    }
    const previewParams = new URLSearchParams({
      preview: "1",
      refresh: String(refreshToken),
    });

    return `${publicBaseUrl}/loja/${encodeURIComponent(tenant.slug)}?${previewParams.toString()}`;
  }, [refreshToken, tenant?.slug]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        setRefreshToken((prev) => prev + 1);
      }
    };

    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  const handleOpenPreview = () => {
    if (!previewUrl) {
      return;
    }
    window.open(previewUrl, "_blank", "noopener,noreferrer");
  };

  const categoriesWithItems = useMemo(() => {
    if (!categoriesQuery.data || !itemsQuery.data) {
      return [];
    }

    const activeItems = itemsQuery.data.filter((item) => item.active);
    return categoriesQuery.data
      .map((category) => ({
        ...category,
        items: activeItems.filter((item) => item.category_id === category.id),
      }))
      .filter((category) => category.items.length > 0);
  }, [categoriesQuery.data, itemsQuery.data]);

  if (isLoading) {
    return <p className="text-sm text-slate-500">Carregando prévia...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (!tenant?.slug) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
        Defina o slug em Minha Loja para ver a prévia.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Prévia do Cardápio (cliente)</CardTitle>
          <div className="flex items-center gap-2">
            <Button onClick={() => setRefreshToken((prev) => prev + 1)} variant="outline">
              Atualizar prévia
            </Button>
            <Button onClick={handleOpenPreview} variant="outline">
              Abrir em nova aba
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-600">
            Visualize como o cliente verá o cardápio público da sua loja.
          </p>
          {previewUrl ? (
            <iframe
              title="Prévia do cardápio público"
              className="h-[80vh] w-full rounded-xl border border-slate-200 bg-white shadow-sm"
              src={previewUrl}
            />
          ) : null}

          <div className="rounded-xl border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-900">Categorias com itens na prévia</h3>
            <p className="mt-1 text-xs text-slate-500">
              Confira abaixo as categorias ativas que possuem itens ativos e devem aparecer no cardápio.
            </p>

            {(categoriesQuery.isLoading || itemsQuery.isLoading) && (
              <p className="mt-3 text-sm text-slate-500">Carregando categorias...</p>
            )}

            {(categoriesQuery.isError || itemsQuery.isError) && (
              <p className="mt-3 text-sm text-red-600">Não foi possível carregar as categorias e itens.</p>
            )}

            {!categoriesQuery.isLoading
              && !itemsQuery.isLoading
              && !categoriesQuery.isError
              && !itemsQuery.isError
              && categoriesWithItems.length === 0 && (
              <p className="mt-3 text-sm text-amber-700">
                Nenhuma categoria com item ativo encontrada. Vincule itens às categorias no módulo Cardápio.
              </p>
            )}

            {categoriesWithItems.length > 0 && (
              <div className="mt-3 space-y-3">
                {categoriesWithItems.map((category) => (
                  <div key={category.id} className="rounded-lg border border-slate-200 p-3">
                    <p className="text-sm font-medium text-slate-900">
                      {category.name} <span className="text-slate-500">({category.items.length})</span>
                    </p>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-600">
                      {category.items.map((item) => (
                        <li key={item.id}>{item.name}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
