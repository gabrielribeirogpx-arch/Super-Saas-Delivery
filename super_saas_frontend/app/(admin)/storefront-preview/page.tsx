"use client";

import { ChevronDown } from "lucide-react";
import { type CSSProperties, type ReactNode, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PublicMenuPage } from "@/components/PublicMenu/PublicMenuPage";
import type { PublicMenuResponse } from "@/components/storefront/types";
import { Button } from "@/components/ui/button";
import { api, apiFetch } from "@/lib/api";

interface PublicSettingsResponse {
  tenant_id: number;
  cover_image_url: string | null;
  cover_video_url: string | null;
  logo_url: string | null;
  theme: string | null;
  primary_color: string | null;
}

interface TenantStoreResponse {
  id: number;
  slug: string;
  estimated_prep_time: string | null;
  business_name?: string;
}

interface AppearanceSettings {
  primary_color: string;
  secondary_color: string;
  button_radius: number;
  font_family: string;
  layout_variant: "clean" | "modern" | "commercial";
}

interface UploadResponse { url: string; }


const validImageTypes = ["image/png", "image/jpeg", "image/webp"];

const DEFAULT_APPEARANCE: AppearanceSettings = {
  primary_color: "#2563eb",
  secondary_color: "#111827",
  button_radius: 12,
  font_family: "Inter",
  layout_variant: "clean",
};

const fontOptions = ["Inter", "DM Sans", "Poppins", "Montserrat", "Roboto", "Lato"];

type ThemeMode = "white" | "dark";

async function getImageDimensions(file: File) {
  const objectUrl = URL.createObjectURL(file);
  try {
    const dimensions = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve({ width: image.width, height: image.height });
      image.onerror = () => reject(new Error("Não foi possível ler a imagem."));
      image.src = objectUrl;
    });
    return dimensions;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function isHexColor(value: string) {
  return /^#([0-9A-Fa-f]{6})$/.test(value);
}

function normalizeStringUrl(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }

  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return "";
  }

  let normalized = trimmedValue;

  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const decoded = decodeURIComponent(normalized);
      if (decoded === normalized) {
        break;
      }
      normalized = decoded;
    } catch {
      break;
    }
  }

  return normalized;
}

export default function StorefrontPreviewPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const [tenantSlug, setTenantSlug] = useState("");
  const [menu, setMenu] = useState<PublicMenuResponse | null>(null);
  const [tenantId, setTenantId] = useState<number | null>(null);

  const [logoUrl, setLogoUrl] = useState("");
  const [coverImageUrl, setCoverImageUrl] = useState("");
  const [coverVideoUrl, setCoverVideoUrl] = useState("");
  const [estimatedPrepTime, setEstimatedPrepTime] = useState("");
  const [theme, setTheme] = useState<ThemeMode>("white");
  const [primaryColor, setPrimaryColor] = useState("#2563eb");
  const [secondaryColor, setSecondaryColor] = useState("#111827");
  const [buttonRadius, setButtonRadius] = useState(12);
  const [fontFamily, setFontFamily] = useState("Inter");
  const [layoutVariant, setLayoutVariant] = useState<AppearanceSettings["layout_variant"]>("clean");
  const [coverMode, setCoverMode] = useState<"image" | "video">("image");

  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [coverImageFile, setCoverImageFile] = useState<File | null>(null);
  const [coverVideoFile, setCoverVideoFile] = useState<File | null>(null);

  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);

  const [logoError, setLogoError] = useState<string | null>(null);
  const [logoWarning, setLogoWarning] = useState<string | null>(null);
  const [coverError, setCoverError] = useState<string | null>(null);
  const [coverWarning, setCoverWarning] = useState<string | null>(null);

  const [uploadingField, setUploadingField] = useState<"logo" | "coverImage" | "coverVideo" | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [openSections, setOpenSections] = useState({
    identity: true,
    colors: true,
    typography: true,
  });

  const [initialSnapshot, setInitialSnapshot] = useState("");

  const requestAppearance = async (method: "GET" | "PUT", payload?: AppearanceSettings) => {
    if (method === "GET") {
      return api.get<AppearanceSettings>("/api/appearance");
    }

    return api.put<AppearanceSettings>("/api/appearance", payload);
  };

  useEffect(() => {
    const fetchData = async () => {
      if (typeof window === "undefined") {
        return;
      }

      try {
        const [publicSettings, store] = await Promise.all([
          api.get<PublicSettingsResponse>("/api/admin/tenant/public-settings"),
          api.get<TenantStoreResponse>("/api/admin/store"),
        ]);

        let appearance = DEFAULT_APPEARANCE;
        try {
          appearance = await requestAppearance("GET");
        } catch (appearanceError) {
          const appearanceStatus =
            typeof appearanceError === "object" && appearanceError !== null && "status" in appearanceError
              ? (appearanceError as { status?: number }).status
              : undefined;

          // A ausência de resposta de aparência não deve forçar logout da sessão,
          // apenas mantém os valores padrão para a prévia.
          if (appearanceStatus && appearanceStatus >= 500) {
            setToast({
              type: "error",
              message: "Não foi possível carregar as configurações de aparência. Usando valores padrão.",
            });
          }
        }

        const nextLogoUrl = normalizeStringUrl(publicSettings.logo_url);
        const nextCoverImageUrl = normalizeStringUrl(publicSettings.cover_image_url);
        const nextCoverVideoUrl = normalizeStringUrl(publicSettings.cover_video_url);

        setTenantId(publicSettings.tenant_id ?? store.id);
        setTenantSlug(store.slug);
        setLogoUrl(nextLogoUrl);
        setCoverImageUrl(nextCoverImageUrl);
        setCoverVideoUrl(nextCoverVideoUrl);
        setEstimatedPrepTime(store.estimated_prep_time ?? "");
        setTheme((publicSettings.theme === "dark" ? "dark" : "white") as ThemeMode);
        setPrimaryColor(publicSettings.primary_color ?? appearance.primary_color ?? DEFAULT_APPEARANCE.primary_color);
        setSecondaryColor(appearance.secondary_color ?? DEFAULT_APPEARANCE.secondary_color);
        setButtonRadius(appearance.button_radius ?? DEFAULT_APPEARANCE.button_radius);
        setFontFamily(appearance.font_family ?? DEFAULT_APPEARANCE.font_family);
        setLayoutVariant(appearance.layout_variant ?? DEFAULT_APPEARANCE.layout_variant);
        setCoverMode(nextCoverVideoUrl && !nextCoverImageUrl ? "video" : "image");

        if (store.slug) {
          const menuResponse = await apiFetch(`/public/menu?slug=${encodeURIComponent(store.slug)}`);
          if (menuResponse.ok) {
            const menuData = (await menuResponse.json()) as PublicMenuResponse;
            setMenu(menuData);
          }
        }

        const snapshot = JSON.stringify({
          logo_url: nextLogoUrl,
          cover_image_url: nextCoverImageUrl,
          cover_video_url: nextCoverVideoUrl,
          estimated_prep_time: store.estimated_prep_time ?? "",
          theme: publicSettings.theme === "dark" ? "dark" : "white",
          primary_color: publicSettings.primary_color ?? appearance.primary_color ?? DEFAULT_APPEARANCE.primary_color,
          secondary_color: appearance.secondary_color ?? DEFAULT_APPEARANCE.secondary_color,
          button_radius: appearance.button_radius ?? DEFAULT_APPEARANCE.button_radius,
          font_family: appearance.font_family ?? DEFAULT_APPEARANCE.font_family,
          layout_variant: appearance.layout_variant ?? DEFAULT_APPEARANCE.layout_variant,
          cover_mode: nextCoverVideoUrl && !nextCoverImageUrl ? "video" : "image",
        });
        setInitialSnapshot(snapshot);
      } catch (err) {
        const status = typeof err === "object" && err !== null && "status" in err
          ? (err as { status?: number }).status
          : undefined;

        if (status === 401) {
          router.push("/login");
          return;
        }

        setError(err instanceof Error ? err.message : "Não foi possível carregar os dados da prévia.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [router]);

  useEffect(() => {
    return () => {
      if (logoPreview) URL.revokeObjectURL(logoPreview);
      if (coverPreview) URL.revokeObjectURL(coverPreview);
    };
  }, [coverPreview, logoPreview]);

  const currentSnapshot = useMemo(
    () =>
      JSON.stringify({
        logo_url: logoUrl,
        cover_image_url: coverImageUrl,
        cover_video_url: coverVideoUrl,
        estimated_prep_time: estimatedPrepTime,
        theme,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        button_radius: buttonRadius,
        font_family: fontFamily,
        layout_variant: layoutVariant,
        cover_mode: coverMode,
      }),
    [
      logoUrl,
      coverImageUrl,
      coverVideoUrl,
      estimatedPrepTime,
      theme,
      primaryColor,
      secondaryColor,
      buttonRadius,
      fontFamily,
      layoutVariant,
      coverMode,
    ],
  );

  const hasUnsavedChanges = currentSnapshot !== initialSnapshot || Boolean(logoFile || coverImageFile || coverVideoFile);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    const handleLinkNavigation = (event: MouseEvent) => {
      if (!hasUnsavedChanges) return;
      const target = event.target as HTMLElement | null;
      const anchor = target?.closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      if (anchor.target === "_blank") return;
      if (!window.confirm("Você tem alterações não salvas. Deseja sair?")) {
        event.preventDefault();
      }
    };

    document.addEventListener("click", handleLinkNavigation, true);
    return () => document.removeEventListener("click", handleLinkNavigation, true);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const previewMenu = useMemo(() => {
    if (!menu) return null;
    return {
      ...menu,
      tenant: {
        ...menu.tenant,
        estimated_prep_time: estimatedPrepTime || menu.tenant.estimated_prep_time,
      },
      public_settings: {
        ...menu.public_settings,
        logo_url: logoPreview ?? logoUrl ?? menu.public_settings?.logo_url,
        cover_image_url: coverMode === "image" ? coverPreview ?? coverImageUrl ?? menu.public_settings?.cover_image_url : null,
        cover_video_url: coverMode === "video" ? coverVideoUrl || menu.public_settings?.cover_video_url : null,
        theme,
        primary_color: primaryColor,
      },
    } as PublicMenuResponse;
  }, [menu, estimatedPrepTime, logoPreview, logoUrl, coverMode, coverPreview, coverImageUrl, coverVideoUrl, theme, primaryColor]);

  const handleOpenPreview = () => {
    if (!tenantSlug) return;
    window.open(`/loja/${encodeURIComponent(tenantSlug)}?preview=1`, "_blank", "noopener,noreferrer");
  };

  const uploadAsset = async (file: File, field: "logo" | "coverImage" | "coverVideo") => {
    if (!tenantId) {
      throw new Error("Loja não identificada para upload.");
    }

    setUploadingField(field);
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams({
      tenant_id: String(tenantId),
      category: "storefront",
      subfolder: field,
    });

    try {
      const response = await apiFetch(`/storefront/upload?${params.toString()}`, { method: "POST", body: formData });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Falha no upload");
      }

      const data = (await response.json()) as UploadResponse;
      return data.url;
    } finally {
      setUploadingField(null);
    }
  };

  const onLogoSelect = async (file: File | null) => {
    setLogoError(null);
    setLogoWarning(null);
    if (!file) {
      setLogoFile(null);
      setLogoPreview(null);
      setLogoUrl("");
      return;
    }

    if (!validImageTypes.includes(file.type)) {
      setLogoError("Formato inválido. Use PNG, JPG ou WebP.");
      return;
    }
    if (file.size > 150 * 1024) {
      setLogoError("Logo excede 150KB.");
      return;
    }

    const { width, height } = await getImageDimensions(file);
    const warnings: string[] = [];
    if (width < 200 || height < 200) warnings.push("Dimensão mínima recomendada: 200×200px.");
    if (width > 400 || height > 400) warnings.push("Dimensão acima da recomendada (400×400px).");
    if (Math.abs(width / height - 1) > 0.02) warnings.push("Proporção ideal: 1:1 (quadrada).");
    setLogoWarning(warnings.join(" "));

    if (logoPreview) URL.revokeObjectURL(logoPreview);
    const nextPreview = URL.createObjectURL(file);
    setLogoPreview(nextPreview);
    setLogoFile(file);
  };

  const onCoverSelect = async (file: File | null) => {
    setCoverError(null);
    setCoverWarning(null);
    if (!file) {
      setCoverImageFile(null);
      setCoverPreview(null);
      setCoverImageUrl("");
      return;
    }

    if (!validImageTypes.includes(file.type)) {
      setCoverError("Formato inválido. Use JPG, PNG ou WebP.");
      return;
    }
    if (file.size > 500 * 1024) {
      setCoverError("A imagem de capa excede 500KB.");
      return;
    }

    const { width, height } = await getImageDimensions(file);
    const ratio = width / height;
    const warnings: string[] = [];
    if (width < 800 || height < 320) warnings.push("Dimensão mínima recomendada: 800×320px.");
    if (Math.abs(ratio - 2.5) > 0.2) warnings.push("Proporção ideal: 5:2.");
    setCoverWarning(warnings.join(" "));

    if (coverPreview) URL.revokeObjectURL(coverPreview);
    const nextPreview = URL.createObjectURL(file);
    setCoverPreview(nextPreview);
    setCoverImageFile(file);
  };

  const handleSave = async () => {
    if (isSaving) {
      return;
    }

    setIsSaving(true);
    setToast(null);
    setError(null);

    try {
      let nextLogo = logoUrl;
      let nextCoverImage = coverImageUrl;
      let nextCoverVideo = coverVideoUrl;

      if (logoFile) {
        nextLogo = await uploadAsset(logoFile, "logo");
      }
      if (coverMode === "image" && coverImageFile) {
        nextCoverImage = await uploadAsset(coverImageFile, "coverImage");
      }
      if (coverMode === "video" && coverVideoFile) {
        nextCoverVideo = await uploadAsset(coverVideoFile, "coverVideo");
      }

      if (coverMode === "image") {
        nextCoverVideo = "";
      } else {
        nextCoverImage = "";
      }

      await api.patch("/api/admin/tenant/public-settings", {
        cover_image_url: nextCoverImage || null,
        cover_video_url: nextCoverVideo || null,
        logo_url: nextLogo || null,
        theme,
        primary_color: primaryColor,
      });

      await api.patch("/api/admin/store", {
        estimated_prep_time: estimatedPrepTime.trim() ? estimatedPrepTime.trim() : null,
      });

      await requestAppearance("PUT", {
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        button_radius: buttonRadius,
        font_family: fontFamily,
        layout_variant: layoutVariant,
      });

      setLogoUrl(nextLogo);
      setCoverImageUrl(nextCoverImage);
      setCoverVideoUrl(nextCoverVideo);
      setLogoFile(null);
      setCoverImageFile(null);
      setCoverVideoFile(null);

      const snapshot = JSON.stringify({
        logo_url: nextLogo,
        cover_image_url: nextCoverImage,
        cover_video_url: nextCoverVideo,
        estimated_prep_time: estimatedPrepTime,
        theme,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        button_radius: buttonRadius,
        font_family: fontFamily,
        layout_variant: layoutVariant,
        cover_mode: coverMode,
      });
      setInitialSnapshot(snapshot);
      setToast({ type: "success", message: "Alterações salvas com sucesso." });
    } catch {
      setToast({ type: "error", message: "Não foi possível salvar as alterações." });
    } finally {
      setUploadingField(null);
      setIsSaving(false);
    }
  };

  if (isLoading) return <p className="text-sm text-slate-500">Carregando prévia...</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  const previewStyle: CSSProperties = {
    ["--accent" as string]: primaryColor,
    ["--accent-text" as string]: primaryColor,
    ["--pill-underline" as string]: primaryColor,
    ["--add-btn-bg" as string]: primaryColor,
    ["--cart-total" as string]: primaryColor,
    ["--badge-special" as string]: secondaryColor,
    ["--button-radius" as string]: `${buttonRadius}px`,
    ["--font-display" as string]: fontFamily,
    ["--font-body" as string]: fontFamily,
  };

  const fileInputClassName =
    "block w-full max-w-full min-w-0 text-xs text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-xs file:font-medium file:text-slate-700 hover:file:bg-slate-200";

  return (
    <div className="flex flex-col lg:flex-row lg:overflow-hidden">
      {toast ? (
        <div className={`fixed right-5 top-5 z-40 rounded-md px-3 py-2 text-sm text-white ${toast.type === "success" ? "bg-emerald-600" : "bg-red-600"}`}>
          {toast.message}
        </div>
      ) : null}

      <aside className="h-[100vh] w-full border-r border-black/10 bg-white lg:w-[380px] lg:flex-shrink-0">
        <div className="h-[calc(100vh-78px)] space-y-4 overflow-y-auto px-5 py-6">
          <Accordion title="Identidade" isOpen={openSections.identity} onToggle={() => setOpenSections((prev) => ({ ...prev, identity: !prev.identity }))}>
            <div className="space-y-2">
              <label className="text-sm font-medium">Logo da loja</label>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className={fileInputClassName}
                onChange={(event) => onLogoSelect(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-slate-500">400×400px • máximo 150KB • PNG/JPG/WebP</p>
              {(logoPreview || logoUrl) ? (
                <div className={`w-fit rounded-xl border p-1 ${logoError ? "border-red-300" : "border-emerald-400"}`}>
                  <img src={logoPreview ?? logoUrl} alt="Preview do logo" className="h-16 w-16 rounded-full object-cover" />
                </div>
              ) : null}
              {(logoPreview || logoUrl) ? <Button variant="outline" onClick={() => onLogoSelect(null)}>Remover</Button> : null}
              {logoError ? <p className="text-xs text-red-600">{logoError}</p> : null}
              {logoWarning ? <p className="text-xs text-amber-600">{logoWarning}</p> : null}
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Imagem de capa</label>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className={fileInputClassName}
                onChange={(event) => onCoverSelect(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-slate-500">1200×480px • proporção 5:2 • máximo 500KB</p>
              {(coverPreview || coverImageUrl) ? (
                <div className={`w-fit rounded-md border p-1 ${coverError ? "border-red-300" : "border-emerald-400"}`}>
                  <img src={coverPreview ?? coverImageUrl} alt="Preview da capa" className="h-20 w-[200px] rounded object-cover" />
                </div>
              ) : null}
              <p className="text-xs text-amber-700">A parte inferior da capa fica coberta pelo nome da loja.</p>
              {(coverPreview || coverImageUrl) ? <Button variant="outline" onClick={() => onCoverSelect(null)}>Remover</Button> : null}
              {coverError ? <p className="text-xs text-red-600">{coverError}</p> : null}
              {coverWarning ? <p className="text-xs text-amber-600">{coverWarning}</p> : null}
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Capa em vídeo (opcional)</label>
              <input
                type="file"
                accept="video/mp4,video/webm"
                className={fileInputClassName}
                onChange={(event) => setCoverVideoFile(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-slate-500">MP4/WEBM recomendado até 2MB.</p>
              {(coverImageUrl || coverPreview) && (coverVideoUrl || coverVideoFile) ? (
                <div className="space-y-1 rounded-md border border-slate-200 p-2 text-xs">
                  <p>Escolha qual capa usar:</p>
                  <label className="mr-3"><input type="radio" checked={coverMode === "image"} onChange={() => setCoverMode("image")} /> Imagem</label>
                  <label><input type="radio" checked={coverMode === "video"} onChange={() => setCoverMode("video")} /> Vídeo</label>
                </div>
              ) : null}
              {(coverVideoUrl || coverVideoFile) ? (
                <Button variant="outline" onClick={() => { setCoverVideoFile(null); setCoverVideoUrl(""); setCoverMode("image"); }}>Remover</Button>
              ) : null}
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Tempo estimado de preparo</label>
              <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" value={estimatedPrepTime} onChange={(event) => setEstimatedPrepTime(event.target.value)} placeholder="Ex: 35 min" />
            </div>
          </Accordion>

          <Accordion title="Cores e Tema" isOpen={openSections.colors} onToggle={() => setOpenSections((prev) => ({ ...prev, colors: !prev.colors }))}>
            <div className="space-y-2">
              <label className="text-sm font-medium">Tema</label>
              <div className="flex rounded-lg border border-slate-200 p-1">
                <button type="button" className={`flex-1 rounded-md px-3 py-2 text-sm ${theme === "white" ? "bg-slate-900 text-white" : "text-slate-700"}`} onClick={() => setTheme("white")}>White ☀</button>
                <button type="button" className={`flex-1 rounded-md px-3 py-2 text-sm ${theme === "dark" ? "bg-slate-900 text-white" : "text-slate-700"}`} onClick={() => setTheme("dark")}>Dark 🌙</button>
              </div>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Cor primária</label>
              <p className="text-xs text-slate-500">Usada em botões, destaques e CTAs</p>
              <div className="flex gap-2">
                <input type="color" value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value)} className="h-10 w-14 rounded border border-slate-200" />
                <input className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm" value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value)} />
              </div>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Cor secundária</label>
              <p className="text-xs text-slate-500">Usada em fundos e elementos de apoio</p>
              <div className="flex gap-2">
                <input type="color" value={secondaryColor} onChange={(event) => setSecondaryColor(event.target.value)} className="h-10 w-14 rounded border border-slate-200" />
                <input className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm" value={secondaryColor} onChange={(event) => setSecondaryColor(event.target.value)} />
              </div>
            </div>
          </Accordion>

          <Accordion title="Tipografia e Layout" isOpen={openSections.typography} onToggle={() => setOpenSections((prev) => ({ ...prev, typography: !prev.typography }))}>
            <div className="space-y-2">
              <label className="text-sm font-medium">Fonte</label>
              <select className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" value={fontFamily} onChange={(event) => setFontFamily(event.target.value)} style={{ fontFamily }}>
                {fontOptions.map((font) => (
                  <option key={font} value={font} style={{ fontFamily: font }}>{font}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Raio do botão ({buttonRadius}px)</label>
              <input type="range" min={0} max={24} value={buttonRadius} onChange={(event) => setButtonRadius(Number(event.target.value))} className="w-full" />
              <button type="button" className="px-4 py-2 text-sm text-white" style={{ borderRadius: buttonRadius, background: primaryColor }}>Botão exemplo</button>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Layout</label>
              <select className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" value={layoutVariant} onChange={(event) => setLayoutVariant(event.target.value as AppearanceSettings["layout_variant"])}>
                <option value="clean">Clean</option>
                <option value="modern">Modern</option>
                <option value="commercial">Commercial</option>
              </select>
            </div>
          </Accordion>
        </div>

        <div className="sticky bottom-0 border-t border-black/10 bg-white px-5 py-4">
          <Button
            className="w-full"
            onClick={handleSave}
            disabled={isSaving || uploadingField !== null || Boolean(logoError || coverError) || !isHexColor(primaryColor) || !isHexColor(secondaryColor)}
          >
            {isSaving || uploadingField ? "Salvando..." : "Salvar alterações"}
          </Button>
        </div>
      </aside>

      <section className="flex-1 px-4 py-6 lg:px-8">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <p className="text-sm font-semibold text-slate-700">Prévia do Cardápio (cliente)</p>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-slate-200 px-2 py-1 text-xs text-slate-600">{theme === "dark" ? "Dark" : "White"}</span>
            <Button variant="outline" onClick={handleOpenPreview}>Abrir em nova aba</Button>
          </div>
        </div>

        <div className="mt-4 flex justify-center">
          <div className="h-[844px] w-[390px] overflow-y-auto rounded-[32px] border border-black/10 bg-white shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            {previewMenu ? (
              <PublicMenuPage menu={previewMenu} enableCart={false} forcedTheme={theme} previewStyle={previewStyle} hideThemeToggle />
            ) : (
              <div className="p-4 text-sm text-slate-500">Carregue um cardápio para visualizar a prévia.</div>
            )}
          </div>
        </div>
        <p className="mt-3 text-center text-xs text-slate-500">Como seu cliente vê a loja</p>
      </section>
    </div>
  );
}

function Accordion({
  title,
  isOpen,
  onToggle,
  children,
}: {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 p-3">
      <button type="button" onClick={onToggle} className="flex w-full items-center justify-between text-left">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>
      {isOpen ? <div className="mt-3 space-y-3">{children}</div> : null}
    </section>
  );
}
