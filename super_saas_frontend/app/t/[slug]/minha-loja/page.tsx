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

export default function MinhaLojaPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [coverImageUrl, setCoverImageUrl] = useState("");
  const [coverVideoUrl, setCoverVideoUrl] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [theme, setTheme] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#0f172a");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["public-settings", slug],
    queryFn: () => api.get<PublicSettingsResponse>("/api/admin/tenant/public-settings"),
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

  const iframeSrc = useMemo(() => `/loja/${slug}?preview=1`, [slug]);

  return (
    <div className="grid gap-6 lg:grid-cols-[360px,1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Minha loja</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Prévia do cardápio</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <iframe
            title="Prévia do cardápio"
            className="h-[720px] w-full border-0"
            src={iframeSrc}
          />
        </CardContent>
      </Card>
    </div>
  );
}
