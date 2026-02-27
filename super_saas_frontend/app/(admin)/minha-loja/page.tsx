"use client";

import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ImageUploadField } from "@/components/admin/ImageUploadField";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, apiFetch } from "@/lib/api";

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
  manual_open_status: boolean;
  estimated_prep_time: string | null;
}

interface UploadResponse {
  url: string;
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
  const [manualOpenStatus, setManualOpenStatus] = useState(true);
  const [estimatedPrepTime, setEstimatedPrepTime] = useState("");
  const [uploadingField, setUploadingField] = useState<"coverImage" | "coverVideo" | "logo" | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["public-settings"],
    queryFn: () => api.get<PublicSettingsResponse>("/api/admin/tenant/public-settings"),
  });

  const tenantQuery = useQuery({
    queryKey: ["tenant", "store-summary"],
    queryFn: () => api.get<TenantResponse>("/api/admin/store"),
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

  useEffect(() => {
    if (!tenantQuery.data) {
      return;
    }
    setManualOpenStatus(tenantQuery.data.manual_open_status ?? true);
    setEstimatedPrepTime(tenantQuery.data.estimated_prep_time ?? "");
  }, [tenantQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      await api.patch<PublicSettingsResponse>("/api/admin/tenant/public-settings", {
        cover_image_url: coverImageUrl || null,
        cover_video_url: coverVideoUrl || null,
        logo_url: logoUrl || null,
        theme: theme || null,
        primary_color: primaryColor || null,
      });

      return api.patch<TenantResponse>("/api/admin/store", {
        estimated_prep_time: estimatedPrepTime.trim() ? estimatedPrepTime.trim() : null,
      });
    },
    onSuccess: () => {
      setStatusMessage("Configurações salvas com sucesso!");
    },
    onError: () => {
      setStatusMessage("Não foi possível salvar as configurações.");
    },
  });


  const storeStatusMutation = useMutation({
    mutationFn: (nextStatus: boolean) =>
      api.patch<TenantResponse>("/api/admin/store/status", {
        manual_open_status: nextStatus,
      }),
    onSuccess: (updatedStore) => {
      setManualOpenStatus(updatedStore.manual_open_status ?? true);
      setStatusMessage(`Loja ${updatedStore.manual_open_status ? "aberta" : "fechada"} com sucesso!`);
    },
    onError: () => {
      setStatusMessage("Não foi possível atualizar o status da loja.");
    },
  });

  const uploadAsset = async (
    file: File | null,
    field: "coverImage" | "coverVideo" | "logo"
  ) => {
    if (!file) {
      if (field === "coverImage") setCoverImageUrl("");
      if (field === "coverVideo") setCoverVideoUrl("");
      if (field === "logo") setLogoUrl("");
      return;
    }

    const tenantId = settingsQuery.data?.tenant_id ?? tenantQuery.data?.id;
    if (!tenantId) {
      setStatusMessage("Não foi possível identificar a loja para fazer upload.");
      return;
    }

    setUploadingField(field);
    setStatusMessage(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const params = new URLSearchParams({
        tenant_id: String(tenantId),
        category: "storefront",
        subfolder: field,
      });

      const response = await apiFetch(`/storefront/upload?${params.toString()}`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Falha no upload");
      }

      const data = (await response.json()) as UploadResponse;
      if (field === "coverImage") setCoverImageUrl(data.url);
      if (field === "coverVideo") setCoverVideoUrl(data.url);
      if (field === "logo") setLogoUrl(data.url);
    } catch {
      setStatusMessage("Não foi possível enviar o arquivo. Tente novamente.");
    } finally {
      setUploadingField(null);
    }
  };

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

  const isStoreActive = manualOpenStatus;

  const handleStoreStatusToggle = (event: ChangeEvent<HTMLInputElement>) => {
    const nextStatus = event.target.checked;
    setManualOpenStatus(nextStatus);
    storeStatusMutation.mutate(nextStatus);
  };

  const handleOpenPreview = () => {
    if (!publicUrl) {
      return;
    }
    window.open(`${publicUrl}?preview=1`, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-2">
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-2">
        <Card className="rounded-2xl border border-gray-200 shadow-sm">
          <CardHeader>
            <CardTitle>Minha loja</CardTitle>
          </CardHeader>
          <CardContent className="p-5 pt-0">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <ImageUploadField
                label="Capa (imagem)"
                accept="image/jpeg,image/png"
                initialPreviewUrl={coverImageUrl || undefined}
                onRemove={() => setCoverImageUrl("")}
                onFileSelect={(file) => uploadAsset(file, "coverImage")}
                instructions={["Recomendado: 1200x600px"]}
              />

              <ImageUploadField
                label="Capa (vídeo)"
                accept="video/mp4,video/webm"
                initialPreviewUrl={coverVideoUrl || undefined}
                onRemove={() => setCoverVideoUrl("")}
                onFileSelect={(file) => uploadAsset(file, "coverVideo")}
                instructions={["Recomendado: MP4/WEBM até 2MB"]}
              />

              <ImageUploadField
                label="Logo"
                accept="image/png,image/jpeg"
                initialPreviewUrl={logoUrl || undefined}
                onRemove={() => setLogoUrl("")}
                onFileSelect={(file) => uploadAsset(file, "logo")}
                instructions={["Recomendado: 400x400px"]}
              />

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

              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="prepTimeInput">
                  Tempo estimado de preparo
                </label>
                <Input
                  type="text"
                  id="prepTimeInput"
                  placeholder="Ex: 25–35 min"
                  value={estimatedPrepTime}
                  onChange={(event) => setEstimatedPrepTime(event.target.value)}
                />
              </div>

              <div className="hidden md:block" />

              {statusMessage && (
                <p className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 md:col-span-2">
                  {statusMessage}
                </p>
              )}

              <div className="md:col-span-2 md:flex md:justify-end">
                <Button
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending || settingsQuery.isLoading || uploadingField !== null}
                >
                  {uploadingField ? "Enviando mídia..." : saveMutation.isPending ? "Salvando..." : "Salvar"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border border-gray-200 shadow-sm">
          <CardHeader>
            <CardTitle>Preview Rápido</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 p-5 pt-0">
            <Button
              onClick={handleOpenPreview}
              variant="outline"
              disabled={!publicUrl}
              className="py-1.5"
            >
              Abrir prévia
            </Button>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">URL pública</p>
              <p className="mt-1 break-all text-sm text-slate-700">
                {publicUrl || "Defina um slug para gerar a URL pública."}
              </p>
            </div>

            <div className="flex items-center gap-3 text-sm text-slate-700">
              <label className="switch">
                <input
                  type="checkbox"
                  id="storeStatusToggle"
                  checked={manualOpenStatus}
                  onChange={handleStoreStatusToggle}
                  disabled={storeStatusMutation.isPending}
                />
                <span className="slider" />
              </label>
              <span
                className={`h-2.5 w-2.5 rounded-full ${isStoreActive ? "bg-emerald-500" : "bg-slate-300"}`}
              />
              <span>
                Status: <strong>{isStoreActive ? "Aberto" : "Fechado"}</strong>
              </span>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Mini mock visual
              </p>
              <div className="space-y-3">
                <div className="h-6 w-2/3 rounded-md bg-slate-200" />
                <div className="h-32 rounded-lg bg-slate-100" />
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
