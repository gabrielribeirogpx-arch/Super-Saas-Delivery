"use client";

import { useMemo, useState } from "react";

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

export default function SettingsPage({ params }: { params: { slug: string } }) {
  const [slug, setSlug] = useState(params.slug ?? "");
  const [customDomain, setCustomDomain] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(
    null
  );

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
      await api.patch<TenantResponse>("/api/admin/tenant", {
        slug,
        custom_domain: customDomain.trim() ? customDomain.trim() : null,
      });
      setStatus({ type: "success", message: "Dados da loja atualizados com sucesso." });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Não foi possível salvar as alterações.";
      setStatus({ type: "error", message });
    } finally {
      setIsSaving(false);
    }
  };

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

          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Salvando..." : "Salvar"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
