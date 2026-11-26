"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AccessDenied } from "@/components/access-denied";
import { isForbiddenError } from "@/components/request-error-state";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { ApiError, api } from "@/lib/api";
import { buildTenantPublicUrl } from "@/lib/platformDomains";

interface TenantResponse {
  id: number;
  slug: string;
  custom_domain: string | null;
  business_name: string;
}

const slugPattern = /^[a-z0-9-]{3,}$/;

export default function SettingsPage() {
  const [slug, setSlug] = useState("");
  const [customDomain, setCustomDomain] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(
    null
  );

  const tenantQuery = useQuery({
    queryKey: ["tenant", "settings"],
    queryFn: () => api.get<TenantResponse>("/api/admin/tenant"),
    retry: false,
  });

  useEffect(() => {
    if (!tenantQuery.data) {
      return;
    }

    setSlug(tenantQuery.data.slug ?? "");
    setCustomDomain(tenantQuery.data.custom_domain ?? "");
  }, [tenantQuery.data]);

  const slugError = useMemo(() => {
    if (!slug) {
      return "Informe o slug da loja.";
    }
    if (!slugPattern.test(slug)) {
      return "Use letras minúsculas, números e hífen (mínimo 3 caracteres).";
    }
    return null;
  }, [slug]);

  const previewSlug = slugPattern.test(slug) ? slug : "seu-slug";

  const handleSave = async () => {
    setStatus(null);
    if (slugError) {
      setStatus({ type: "error", message: slugError });
      return;
    }
    setIsSaving(true);
    try {
      const updatedTenant = await api.patch<TenantResponse>("/api/admin/tenant", {
        slug,
        custom_domain: customDomain.trim() ? customDomain.trim() : null,
      });
      setSlug(updatedTenant.slug ?? "");
      setCustomDomain(updatedTenant.custom_domain ?? "");
      setStatus({ type: "success", message: "Dados da loja atualizados com sucesso." });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Não foi possível salvar as alterações.";
      setStatus({ type: "error", message });
    } finally {
      setIsSaving(false);
    }
  };

  if (tenantQuery.isLoading) {
    return <LoadingExperience label="Preparando as configurações" />;
  }

  if (isForbiddenError(tenantQuery.error)) return <AccessDenied />;

  if (tenantQuery.isError) {
    return <p className="text-sm text-red-600">Não foi possível carregar as configurações da loja atual.</p>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Minha Loja</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="slug">
              Slug
            </label>
            <Input
              id="slug"
              value={slug}
              onChange={(event) => setSlug(event.target.value.toLowerCase())}
              placeholder="minha-loja"
            />
            <p className="text-xs text-slate-500">
              Preview: {buildTenantPublicUrl(previewSlug)}
            </p>
            {slugError && <p className="text-xs text-red-600">{slugError}</p>}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="custom-domain">
              Domínio personalizado (opcional)
            </label>
            <Input
              id="custom-domain"
              value={customDomain}
              onChange={(event) => setCustomDomain(event.target.value)}
              placeholder="www.sualoja.com.br"
            />
          </div>

          {status && (
            <p
              className={
                status.type === "success"
                  ? "text-sm text-emerald-600"
                  : "text-sm text-red-600"
              }
            >
              {status.message}
            </p>
          )}

          <Button onClick={handleSave} disabled={isSaving || tenantQuery.isLoading}>
            {isSaving ? "Salvando..." : "Salvar"}
          </Button>
        </CardContent>
      </Card>
      <PrinterSettings />
    </div>
  );
}

type PaperWidth = 58 | 80;

function PrinterSettings() {
  const queryClient = useQueryClient();
  const [selectedWidth, setSelectedWidth] = useState<PaperWidth | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const settings = useQuery({
    queryKey: ["tenant", "printing"],
    queryFn: () => api.get<{ paper_width_mm: PaperWidth }>("/api/admin/tenant/printing"),
    retry: false,
  });
  const width = selectedWidth ?? settings.data?.paper_width_mm;

  const save = async () => {
    if (!width) return;
    setSaving(true);
    setFeedback("");
    try {
      const saved = await api.put<{ paper_width_mm: PaperWidth }>("/api/admin/tenant/printing", { paper_width_mm: width });
      queryClient.setQueryData(["tenant", "printing"], saved);
      setSelectedWidth(null);
      setFeedback("Formato de impressão salvo.");
    } catch {
      setFeedback("Não foi possível salvar. Tente novamente.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle>Impressora de etiquetas</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {settings.isLoading ? <p role="status" className="text-sm text-slate-600">Carregando formato de impressão…</p> : settings.isError ? (
          <div className="space-y-2">
            <p role="alert" className="text-sm text-slate-600">Não foi possível carregar o formato de impressão.</p>
            <Button variant="outline" onClick={() => void settings.refetch()}>Tentar novamente</Button>
          </div>
        ) : (
          <>
            <div className="max-w-xs space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="ticket-paper-width">Largura da bobina</label>
              <Select id="ticket-paper-width" value={width} disabled={saving} onChange={(event) => {
                setSelectedWidth(event.target.value === "58" ? 58 : 80);
                setFeedback("");
              }}>
                <option value={80}>80 mm</option>
                <option value={58}>58 mm</option>
              </Select>
            </div>
            <p className="text-sm text-slate-600">Abra a etiqueta de teste, escolha a impressora no diálogo do computador e imprima em tamanho real (100%).</p>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={save} disabled={saving}>{saving ? "Salvando…" : "Salvar formato"}</Button>
              <Button asChild variant="outline">
                <a href={`/api/admin/tenant/printing/test?paper_width_mm=${width}`} target="_blank" rel="noopener noreferrer">Abrir etiqueta de teste</a>
              </Button>
            </div>
            {feedback && <p role="status" className="text-sm text-slate-700">{feedback}</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}
