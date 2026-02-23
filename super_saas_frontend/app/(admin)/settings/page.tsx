"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, api } from "@/lib/api";

interface TenantResponse {
  id: number;
  slug: string;
  custom_domain: string | null;
  business_name: string;
}

interface AppearanceResponse {
  tenant_id: number;
  primary_color: string;
  secondary_color: string;
  hero_mode: string;
  hero_title: string;
  hero_subtitle: string;
  logo_url: string;
  cover_url: string;
  button_style: string;
  layout_mode: string;
}

const slugPattern = /^[a-z0-9-]{3,}$/;

const defaultAppearance: AppearanceResponse = {
  tenant_id: 0,
  primary_color: "#2563eb",
  secondary_color: "#111827",
  hero_mode: "commercial",
  hero_title: "",
  hero_subtitle: "",
  logo_url: "",
  cover_url: "",
  button_style: "rounded",
  layout_mode: "hybrid",
};

export default function SettingsPage() {
  const [slug, setSlug] = useState("");
  const [customDomain, setCustomDomain] = useState("");
  const [appearance, setAppearance] = useState<AppearanceResponse>(defaultAppearance);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    const loadAppearance = async () => {
      try {
        const data = await api.get<AppearanceResponse>("/api/store/appearance");
        setAppearance(data);
      } catch {
        setAppearance(defaultAppearance);
      }
    };
    loadAppearance();
  }, []);

  const slugError = useMemo(() => {
    if (!slug) return "Informe o slug da loja.";
    if (!slugPattern.test(slug)) return "Use letras minúsculas, números e hífen (mínimo 3 caracteres).";
    return null;
  }, [slug]);

  const previewSlug = slugPattern.test(slug) ? slug : "seu-slug";

  const handleSaveStore = async () => {
    setStatus(null);
    if (slugError) return setStatus({ type: "error", message: slugError });
    setIsSaving(true);
    try {
      await api.patch<TenantResponse>("/api/admin/tenant", {
        slug,
        custom_domain: customDomain.trim() ? customDomain.trim() : null,
      });
      setStatus({ type: "success", message: "Dados da loja atualizados com sucesso." });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Não foi possível salvar as alterações.";
      setStatus({ type: "error", message });
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAppearance = async () => {
    setStatus(null);
    setIsSaving(true);
    try {
      const saved = await api.put<AppearanceResponse>("/api/store/appearance", appearance);
      setAppearance(saved);
      setStatus({ type: "success", message: "Appearance salva com sucesso." });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Falha ao salvar Appearance.";
      setStatus({ type: "error", message });
    } finally {
      setIsSaving(false);
    }
  };

  const uploadAsDataUrl = (file: File, target: "logo_url" | "cover_url") => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = typeof reader.result === "string" ? reader.result : "";
      setAppearance((prev) => ({ ...prev, [target]: value }));
    };
    reader.readAsDataURL(file);
  };

  return (
    <Tabs defaultValue="store" className="space-y-6">
      <TabsList>
        <TabsTrigger value="store">Minha Loja</TabsTrigger>
        <TabsTrigger value="appearance">Appearance</TabsTrigger>
      </TabsList>

      <TabsContent value="store">
        <Card>
          <CardHeader><CardTitle>Minha Loja</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Slug</label>
              <Input value={slug} onChange={(event) => setSlug(event.target.value.toLowerCase())} placeholder="minha-loja" />
              <p className="text-xs text-slate-500">Preview: https://{previewSlug}.mandarpedido.com</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Domínio personalizado (opcional)</label>
              <Input value={customDomain} onChange={(event) => setCustomDomain(event.target.value)} placeholder="www.sualoja.com.br" />
            </div>
            <Button onClick={handleSaveStore} disabled={isSaving}>{isSaving ? "Salvando..." : "Salvar"}</Button>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="appearance">
        <Card>
          <CardHeader><CardTitle>Appearance</CardTitle></CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2"><label className="text-sm">Cor primária</label><Input type="color" value={appearance.primary_color} onChange={(e) => setAppearance((p) => ({ ...p, primary_color: e.target.value }))} /></div>
            <div className="space-y-2"><label className="text-sm">Cor secundária</label><Input type="color" value={appearance.secondary_color} onChange={(e) => setAppearance((p) => ({ ...p, secondary_color: e.target.value }))} /></div>
            <div className="space-y-2 md:col-span-2"><label className="text-sm">Hero title</label><Input value={appearance.hero_title} onChange={(e) => setAppearance((p) => ({ ...p, hero_title: e.target.value }))} /></div>
            <div className="space-y-2 md:col-span-2"><label className="text-sm">Hero subtitle</label><Input value={appearance.hero_subtitle} onChange={(e) => setAppearance((p) => ({ ...p, hero_subtitle: e.target.value }))} /></div>
            <div className="space-y-2"><label className="text-sm">Layout mode</label><select className="h-10 w-full rounded-md border border-slate-200 px-3" value={appearance.layout_mode} onChange={(e) => setAppearance((p) => ({ ...p, layout_mode: e.target.value }))}><option value="minimal">Minimal</option><option value="commercial">Commercial</option><option value="hybrid">Hybrid</option></select></div>
            <div className="space-y-2"><label className="text-sm">Hero mode</label><select className="h-10 w-full rounded-md border border-slate-200 px-3" value={appearance.hero_mode} onChange={(e) => setAppearance((p) => ({ ...p, hero_mode: e.target.value }))}><option value="minimal">Minimal</option><option value="commercial">Commercial</option></select></div>
            <div className="space-y-2"><label className="text-sm">Upload de logo</label><Input type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && uploadAsDataUrl(e.target.files[0], "logo_url")} /></div>
            <div className="space-y-2"><label className="text-sm">Upload de capa</label><Input type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && uploadAsDataUrl(e.target.files[0], "cover_url")} /></div>
            <div className="space-y-2 md:col-span-2"><label className="text-sm">URL do logo (opcional)</label><Input value={appearance.logo_url} onChange={(e) => setAppearance((p) => ({ ...p, logo_url: e.target.value }))} /></div>
            <div className="space-y-2 md:col-span-2"><label className="text-sm">URL da capa (opcional)</label><Input value={appearance.cover_url} onChange={(e) => setAppearance((p) => ({ ...p, cover_url: e.target.value }))} /></div>
            <div className="md:col-span-2"><Button onClick={handleSaveAppearance} disabled={isSaving}>{isSaving ? "Salvando..." : "Salvar Appearance"}</Button></div>
          </CardContent>
        </Card>
      </TabsContent>

      {status && <p className={status.type === "success" ? "text-sm text-emerald-600" : "text-sm text-red-600"}>{status.message}</p>}
    </Tabs>
  );
}
