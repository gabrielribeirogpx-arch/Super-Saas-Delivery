"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, api, apiFetch } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/media";
import { type AppearanceTheme, useAppearanceEditor } from "@/hooks/use-appearance-editor";

interface ToastState {
  type: "success" | "error";
  message: string;
}

interface TenantData {
  business_name: string;
}

const FALLBACKS = {
  primary: "#111827",
  accent: "#1d4ed8",
  background: "#f8fafc",
  surface: "#ffffff",
  buttonRadius: 12,
  cardRadius: 18,
  overlay: 0.55,
};

export default function AppearancePage() {
  const [toast, setToast] = useState<ToastState | null>(null);
  const [storeName, setStoreName] = useState("Minha Loja");
  const [subtitle, setSubtitle] = useState("Seu sabor, sua identidade visual.");

  const { draftTheme, setDraftTheme, setFromRemote, save, reset, isDirty, isSaving } =
    useAppearanceEditor();

  const themeQuery = useQuery({
    queryKey: ["store-theme"],
    queryFn: () => api.get<AppearanceTheme>("/api/store/theme"),
  });

  const tenantQuery = useQuery({
    queryKey: ["current-tenant"],
    queryFn: () => api.get<TenantData>("/api/admin/tenant"),
  });

  useEffect(() => {
    if (themeQuery.data) {
      setFromRemote(themeQuery.data);
    }
  }, [themeQuery.data, setFromRemote]);

  useEffect(() => {
    if (tenantQuery.data?.business_name) {
      setStoreName(tenantQuery.data.business_name);
    }
  }, [tenantQuery.data]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  const previewTheme = useMemo(
    () => ({
      primary: draftTheme.primary_color ?? FALLBACKS.primary,
      accent: draftTheme.accent_color ?? FALLBACKS.accent,
      background: draftTheme.background_color ?? FALLBACKS.background,
      surface: draftTheme.surface_color ?? FALLBACKS.surface,
      buttonRadius: draftTheme.button_radius ?? FALLBACKS.buttonRadius,
      cardRadius: draftTheme.card_radius ?? FALLBACKS.cardRadius,
      overlay: draftTheme.hero_overlay_opacity ?? FALLBACKS.overlay,
      cover: resolveMediaUrl(draftTheme.cover_image_url),
      logo: resolveMediaUrl(draftTheme.logo_url),
    }),
    [draftTheme]
  );

  const setThemeValue = <K extends keyof AppearanceTheme>(key: K, value: AppearanceTheme[K]) => {
    setDraftTheme((current) => ({ ...current, [key]: value }));
  };

  const uploadImage = async (file: File, key: "cover_image_url" | "logo_url") => {
    const formData = new FormData();
    formData.append("image", file);
    const response = await apiFetch("/api/store/theme/upload", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) {
      throw new ApiError((data as { detail?: string }).detail ?? "Falha no upload", response.status, data);
    }
    setThemeValue(key, data.url as string);
  };

  const handleSave = async () => {
    try {
      await save();
      setToast({ type: "success", message: "Aparência salva com sucesso." });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Não foi possível salvar a aparência.";
      setToast({ type: "error", message });
    }
  };

  if (themeQuery.isLoading) {
    return <p className="text-sm text-slate-500">Carregando aparência...</p>;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-800">Identidade Visual</h3>
            <Input value={storeName} onChange={(event) => setStoreName(event.target.value)} placeholder="Nome da loja" />
            <Input value={subtitle} onChange={(event) => setSubtitle(event.target.value)} placeholder="Subtítulo comercial" />
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm">
                Upload capa
                <Input type="file" accept="image/*" onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  uploadImage(file, "cover_image_url").catch(() => {
                    setToast({ type: "error", message: "Falha ao enviar imagem de capa." });
                  });
                }} />
              </label>
              <label className="text-sm">
                Upload logo
                <Input type="file" accept="image/*" onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  uploadImage(file, "logo_url").catch(() => {
                    setToast({ type: "error", message: "Falha ao enviar logo." });
                  });
                }} />
              </label>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-800">Cores</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm">Primária<Input type="color" value={previewTheme.primary} onChange={(event) => setThemeValue("primary_color", event.target.value)} /></label>
              <label className="text-sm">Secundária<Input type="color" value={previewTheme.accent} onChange={(event) => setThemeValue("accent_color", event.target.value)} /></label>
              <label className="text-sm">Fundo<Input type="color" value={previewTheme.background} onChange={(event) => setThemeValue("background_color", event.target.value)} /></label>
              <label className="text-sm">Surface<Input type="color" value={previewTheme.surface} onChange={(event) => setThemeValue("surface_color", event.target.value)} /></label>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-800">Estilo</h3>
            <label className="block text-sm">Radius botão: {previewTheme.buttonRadius}px
              <input className="w-full" type="range" min={6} max={32} value={previewTheme.buttonRadius} onChange={(event) => setThemeValue("button_radius", Number(event.target.value))} />
            </label>
            <label className="block text-sm">Radius card: {previewTheme.cardRadius}px
              <input className="w-full" type="range" min={6} max={32} value={previewTheme.cardRadius} onChange={(event) => setThemeValue("card_radius", Number(event.target.value))} />
            </label>
            <label className="block text-sm">Overlay hero: {previewTheme.overlay.toFixed(2)}
              <input className="w-full" type="range" step={0.05} min={0} max={0.9} value={previewTheme.overlay} onChange={(event) => setThemeValue("hero_overlay_opacity", Number(event.target.value))} />
            </label>
          </section>

          <div className="flex gap-3">
            <Button onClick={handleSave} disabled={!isDirty || isSaving}>{isSaving ? "Salvando..." : "Salvar alterações"}</Button>
            <Button variant="outline" onClick={reset} disabled={!isDirty || isSaving}>Resetar</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Preview lateral</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            className="mx-auto w-[260px] rounded-[28px] border border-slate-200 p-3"
            style={{ background: previewTheme.background }}
          >
            <div className="overflow-hidden rounded-2xl" style={{ background: previewTheme.surface }}>
              <div
                className="relative h-32"
                style={{
                  backgroundImage: previewTheme.cover
                    ? `linear-gradient(rgba(15,23,42,${previewTheme.overlay}), rgba(15,23,42,${previewTheme.overlay})), url(${previewTheme.cover})`
                    : `linear-gradient(135deg, ${previewTheme.primary}, ${previewTheme.accent})`,
                  backgroundSize: "cover",
                  backgroundPosition: "center",
                }}
              />
              <div className="-mt-6 px-4 pb-4">
                <div className="mb-2 h-12 w-12 overflow-hidden rounded-full border-2 border-white bg-white">
                  {previewTheme.logo ? <img src={previewTheme.logo} alt="logo" className="h-full w-full object-cover" /> : null}
                </div>
                <p className="font-semibold" style={{ color: previewTheme.primary }}>{storeName}</p>
                <p className="text-xs text-slate-500">{subtitle}</p>
                <button
                  className="mt-3 w-full px-3 py-2 text-sm font-medium text-white"
                  style={{ background: previewTheme.accent, borderRadius: previewTheme.buttonRadius }}
                  type="button"
                >
                  Fazer pedido
                </button>
                <div className="mt-3 border p-3 text-xs text-slate-600" style={{ borderRadius: previewTheme.cardRadius }}>
                  Preview mobile isolado com CSS vars temporárias.
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {toast && (
        <div className={`fixed bottom-5 right-5 rounded-lg px-4 py-3 text-sm text-white ${toast.type === "success" ? "bg-emerald-600" : "bg-red-600"}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
