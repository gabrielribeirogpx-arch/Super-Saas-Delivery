"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

interface PublicSettingsResponse {
  tenant_id: number;
  cover_image_url: string | null;
  cover_video_url: string | null;
  logo_url: string | null;
  theme: string | null;
  primary_color: string | null;
}

interface TenantResponse {
  id: number;
  slug: string;
  custom_domain: string | null;
}

const getPublicBaseUrl = () => {
  if (typeof window === "undefined") {
    return "";
  }
  return window.location.origin;
};

export default function MinhaLojaPage() {
  const [coverImageUrl, setCoverImageUrl] = useState("");
  const [coverVideoUrl, setCoverVideoUrl] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [theme, setTheme] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#0f172a");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["public-settings"],
    queryFn: () => api.get<PublicSettingsResponse>("/api/admin/tenant/public-settings"),
  });

  const tenantQuery = useQuery({
    queryKey: ["tenant", "store-summary"],
    queryFn: () => api.get<TenantResponse>("/api/admin/tenant"),
  });

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    setCoverImageUrl(settingsQuery.data.cover_image_url ?? "");
    setCoverVideoUrl(settingsQuery.data.cover_video_url ?? "");
    setLogoUrl(settingsQuery.data.logo_url ?? "");
    setTheme(settingsQuery.data.theme ?? "");
    setPrimaryColor(settingsQuery.data.primary_color ?? "#0f172a");
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.patch<PublicSettingsResponse>("/api/admin/tenant/public-settings", {
        cover_image_url: coverImageUrl || null,
        cover_video_url: coverVideoUrl || null,
        logo_url: logoUrl || null,
        theme: theme || null,
        primary_color: primaryColor || null,
      }),
    onSuccess: () => {
      setStatusMessage("Configurações salvas com sucesso!");
    },
    onError: () => {
      setStatusMessage("Não foi possível salvar as configurações.");
    },
  });

  const publicUrl = useMemo(() => {
    const slug = tenantQuery.data?.slug;
    if (!slug) {
      return "";
    }

    const baseUrl = getPublicBaseUrl();
    if (!baseUrl) {
      return "";
    }

    return `${baseUrl}/loja/${encodeURIComponent(slug)}`;
  }, [tenantQuery.data?.slug]);

  const isStoreActive = Boolean(tenantQuery.data?.slug);

  const handleOpenPreview = () => {
    if (!publicUrl) {
      return;
    }
    window.open(`${publicUrl}?preview=1`, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-2">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <Card className="rounded-2xl border border-gray-200 shadow-sm">
          <CardHeader>
            <CardTitle>Minha loja</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 p-6 pt-0">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Capa (imagem)</label>
              <Input
                placeholder="https://..."
                value={coverImageUrl}
                onChange={(event) => setCoverImageUrl(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Capa (vídeo)</label>
              <Input
                placeholder="https://..."
                value={coverVideoUrl}
                onChange={(event) => setCoverVideoUrl(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Logo</label>
              <Input
                placeholder="https://..."
                value={logoUrl}
                onChange={(event) => setLogoUrl(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Tema</label>
              <Input
                placeholder="claro, escuro..."
                value={theme}
                onChange={(event) => setTheme(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Cor primária</label>
              <Input
                type="color"
                value={primaryColor}
                onChange={(event) => setPrimaryColor(event.target.value)}
                className="h-10 p-1"
              />
            </div>

            {statusMessage && (
              <p className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                {statusMessage}
              </p>
            )}

            <Button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || settingsQuery.isLoading}
            >
              {saveMutation.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border border-gray-200 shadow-sm">
          <CardHeader>
            <CardTitle>Preview Rápido</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5 p-6 pt-0">
            <Button onClick={handleOpenPreview} variant="outline" disabled={!publicUrl}>
              Abrir prévia
            </Button>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">URL pública</p>
              <p className="mt-1 break-all text-sm text-slate-700">{publicUrl || "Defina um slug para gerar a URL pública."}</p>
            </div>

            <div className="flex items-center gap-2 text-sm text-slate-700">
              <span
                className={`h-2.5 w-2.5 rounded-full ${isStoreActive ? "bg-emerald-500" : "bg-slate-300"}`}
              />
              <span>
                Status: <strong>{isStoreActive ? "Ativa" : "Inativa"}</strong>
              </span>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Mini mock visual
              </p>
              <div className="space-y-3">
                <div className="h-6 w-2/3 rounded-md bg-slate-200" />
                <div className="h-20 rounded-lg bg-slate-100" />
                <div className="grid grid-cols-2 gap-2">
                  <div className="h-10 rounded-md bg-slate-100" />
                  <div className="h-10 rounded-md bg-slate-100" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
