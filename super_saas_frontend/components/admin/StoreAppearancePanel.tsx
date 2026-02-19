"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

interface StoreThemeResponse {
  primary_color: string | null;
  secondary_color: string | null;
  logo_url: string | null;
  cover_url: string | null;
  slogan: string | null;
  show_logo_on_cover: boolean;
  updated_at: string | null;
}

const DEFAULT_PRIMARY_COLOR = "#2563EB";

const fileToDataUrl = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("Falha ao processar arquivo."));
    reader.readAsDataURL(file);
  });

export function StoreAppearancePanel() {
  const [primaryColor, setPrimaryColor] = useState(DEFAULT_PRIMARY_COLOR);
  const [secondaryColor, setSecondaryColor] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [coverUrl, setCoverUrl] = useState("");
  const [slogan, setSlogan] = useState("");
  const [showLogoOnCover, setShowLogoOnCover] = useState(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const themeQuery = useQuery({
    queryKey: ["store-theme"],
    queryFn: () => api.get<StoreThemeResponse>("/api/store/theme"),
  });

  useEffect(() => {
    if (!themeQuery.data) return;
    setPrimaryColor(themeQuery.data.primary_color ?? DEFAULT_PRIMARY_COLOR);
    setSecondaryColor(themeQuery.data.secondary_color ?? "");
    setLogoUrl(themeQuery.data.logo_url ?? "");
    setCoverUrl(themeQuery.data.cover_url ?? "");
    setSlogan(themeQuery.data.slogan ?? "");
    setShowLogoOnCover(themeQuery.data.show_logo_on_cover);
  }, [themeQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put<StoreThemeResponse>("/api/store/theme", {
        primary_color: primaryColor,
        secondary_color: secondaryColor || null,
        logo_url: logoUrl || null,
        cover_url: coverUrl || null,
        slogan: slogan || null,
        show_logo_on_cover: showLogoOnCover,
      }),
    onSuccess: () => setStatusMessage("Aparência salva com sucesso."),
    onError: () => setStatusMessage("Não foi possível salvar a aparência."),
  });

  const handleFileUpload =
    (setter: (value: string) => void) => async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const dataUrl = await fileToDataUrl(file);
      setter(dataUrl);
    };

  return (
    <Card>
      <CardHeader>
        <CardTitle>🎨 Aparência da Loja</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Cor primária</label>
            <Input type="color" value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)} className="h-10 p-1" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Cor secundária (opcional)</label>
            <Input type="color" value={secondaryColor || "#ffffff"} onChange={(e) => setSecondaryColor(e.target.value)} className="h-10 p-1" />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">Upload de logo</label>
          <Input type="file" accept="image/*" onChange={handleFileUpload(setLogoUrl)} />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">Upload de imagem de capa</label>
          <Input type="file" accept="image/*" onChange={handleFileUpload(setCoverUrl)} />
        </div>

        <div className="flex items-center justify-between rounded-md border border-slate-200 p-3">
          <label className="text-sm font-medium text-slate-700">Mostrar logo na capa</label>
          <input
            type="checkbox"
            checked={showLogoOnCover}
            onChange={(event) => setShowLogoOnCover(event.target.checked)}
            className="h-4 w-4"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">Texto slogan (opcional)</label>
          <Input value={slogan} onChange={(event) => setSlogan(event.target.value)} placeholder="Seu slogan" />
        </div>

        {statusMessage ? <p className="text-sm text-slate-600">{statusMessage}</p> : null}

        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || themeQuery.isLoading}>
          {saveMutation.isPending ? "Salvando..." : "Salvar alterações"}
        </Button>
      </CardContent>
    </Card>
  );
}
