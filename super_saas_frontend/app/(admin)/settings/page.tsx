"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";

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
    return <p className="text-sm text-slate-500">Carregando configurações...</p>;
  }

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
              Preview: https://{previewSlug}.mandarpedido.com
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
    </div>
  );
}
