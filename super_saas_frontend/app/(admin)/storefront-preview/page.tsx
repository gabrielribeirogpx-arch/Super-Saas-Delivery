"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

interface TenantResponse {
  id: number;
  slug: string;
  custom_domain: string | null;
  business_name: string;
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
        </CardContent>
      </Card>
    </div>
  );
}
