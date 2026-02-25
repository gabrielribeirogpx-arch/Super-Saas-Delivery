"use client";

import { useEffect, useMemo, useState } from "react";
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
  is_open: boolean;
  estimated_time_min: number | null;
  banner_blur_enabled: boolean;
  banner_blur_intensity: number | null;
  banner_overlay_opacity: number | null;
}

interface TenantResponse {
  id: number;
  slug: string;
  custom_domain: string | null;
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
  const [isOpen, setIsOpen] = useState(true);
  const [estimatedTimeMin, setEstimatedTimeMin] = useState("30");
  const [bannerBlurEnabled, setBannerBlurEnabled] = useState(true);
  const [bannerBlurIntensity, setBannerBlurIntensity] = useState("6");
  const [bannerOverlayOpacity, setBannerOverlayOpacity] = useState("0.55");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [uploadingField, setUploadingField] = useState<"coverImage" | "coverVideo" | "logo" | null>(null);

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
    setIsOpen(settingsQuery.data.is_open ?? true);
    setEstimatedTimeMin(String(settingsQuery.data.estimated_time_min ?? 30));
    setBannerBlurEnabled(settingsQuery.data.banner_blur_enabled ?? true);
    setBannerBlurIntensity(String(settingsQuery.data.banner_blur_intensity ?? 6));
    setBannerOverlayOpacity(String(settingsQuery.data.banner_overlay_opacity ?? 0.55));
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.patch<PublicSettingsResponse>("/api/admin/tenant/public-settings", {
        cover_image_url: coverImageUrl || null,
        cover_video_url: coverVideoUrl || null,
        logo_url: logoUrl || null,
        theme: theme || null,
        primary_color: primaryColor || null,
        is_open: isOpen,
        estimated_time_min: Number(estimatedTimeMin) || null,
        banner_blur_enabled: bannerBlurEnabled,
        banner_blur_intensity: Number(bannerBlurIntensity) || 0,
        banner_overlay_opacity: Number(bannerOverlayOpacity) || 0,
      }),
    onSuccess: () => {
      setStatusMessage("Configurações salvas com sucesso!");
    },
    onError: () => {
      setStatusMessage("Não foi possível salvar as configurações.");
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

  const isStoreActive = Boolean(tenantQuery.data?.slug);

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

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Status da loja</label>
                <select className="h-10 w-full rounded-md border border-slate-200 px-3" value={isOpen ? "open" : "closed"} onChange={(event) => setIsOpen(event.target.value === "open")}>
                  <option value="open">Aberto agora</option>
                  <option value="closed">Fechado</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Tempo estimado (min)</label>
                <Input type="number" min="5" max="120" value={estimatedTimeMin} onChange={(event) => setEstimatedTimeMin(event.target.value)} />
              </div>

              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <input type="checkbox" checked={bannerBlurEnabled} onChange={(event) => setBannerBlurEnabled(event.target.checked)} />
                  Blur do banner habilitado
                </label>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Intensidade do blur</label>
                <Input type="number" min="0" max="32" value={bannerBlurIntensity} onChange={(event) => setBannerBlurIntensity(event.target.value)} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Opacidade do overlay (0-1)</label>
                <Input type="number" min="0" max="1" step="0.05" value={bannerOverlayOpacity} onChange={(event) => setBannerOverlayOpacity(event.target.value)} />
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
