"use client";

import { ChevronDown, Eye, SlidersHorizontal } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { PublicMenuResponse } from "@/components/storefront/types";
import { Button } from "@/components/ui/button";
import { LoadingExperience } from "@/components/ui/loading-experience";
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


const MB = 1024 * 1024;
const validImageTypes = ["image/png", "image/jpeg", "image/webp"];
const validVideoTypes = ["video/mp4", "video/webm"];
const LOGO_MAX_SIZE_BYTES = 1 * MB;
const COVER_IMAGE_MAX_SIZE_BYTES = 5 * MB;
const COVER_VIDEO_MAX_SIZE_BYTES = 20 * MB;

const DEFAULT_APPEARANCE: AppearanceSettings = {
  primary_color: "#dc2626",
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
  const [primaryColor, setPrimaryColor] = useState("#dc2626");
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
  const [previewWidth, setPreviewWidth] = useState<390 | 520>(520);
  const [mobileView, setMobileView] = useState<"edit" | "preview">("edit");
  const previewFrameRef = useRef<HTMLIFrameElement>(null);

  const [openSections, setOpenSections] = useState({
    identity: true,
    colors: false,
    typography: false,
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
        let menuData: PublicMenuResponse | null = null;
        if (store.slug) {
          const menuResponse = await apiFetch(`/api/public/menu?slug=${encodeURIComponent(store.slug)}`);
          if (menuResponse.ok) {
            menuData = (await menuResponse.json()) as PublicMenuResponse;
            setMenu(menuData);
          } else {
            setToast({ type: "error", message: "Não foi possível carregar o cardápio. Tente novamente." });
          }
        }
        // The public endpoint resolves legacy presets. The editor must start from that same result.
        const effectiveTheme = (menuData?.public_settings?.theme ?? publicSettings.theme) === "dark" ? "dark" : "white";
        const effectivePrimaryColor = menuData?.public_settings?.primary_color ?? appearance.primary_color ?? publicSettings.primary_color ?? DEFAULT_APPEARANCE.primary_color;
        const effectiveSecondaryColor = menuData?.public_settings?.secondary_color ?? appearance.secondary_color ?? DEFAULT_APPEARANCE.secondary_color;
        const effectiveButtonRadius = menuData?.public_settings?.button_radius ?? appearance.button_radius ?? DEFAULT_APPEARANCE.button_radius;
        const effectiveFontFamily = menuData?.public_settings?.font_family ?? appearance.font_family ?? DEFAULT_APPEARANCE.font_family;
        const effectiveLayoutVariant = menuData?.public_settings?.layout_variant ?? appearance.layout_variant ?? DEFAULT_APPEARANCE.layout_variant;

        setTenantId(publicSettings.tenant_id ?? store.id);
        setTenantSlug(store.slug);
        setLogoUrl(nextLogoUrl);
        setCoverImageUrl(nextCoverImageUrl);
        setCoverVideoUrl(nextCoverVideoUrl);
        setEstimatedPrepTime(store.estimated_prep_time ?? "");
        setTheme(effectiveTheme);
        setPrimaryColor(effectivePrimaryColor);
        setSecondaryColor(effectiveSecondaryColor);
        setButtonRadius(effectiveButtonRadius);
        setFontFamily(effectiveFontFamily);
        setLayoutVariant(effectiveLayoutVariant);
        setCoverMode(nextCoverVideoUrl && !nextCoverImageUrl ? "video" : "image");

        const snapshot = JSON.stringify({
          logo_url: nextLogoUrl,
          cover_image_url: nextCoverImageUrl,
          cover_video_url: nextCoverVideoUrl,
          estimated_prep_time: store.estimated_prep_time ?? "",
          theme: effectiveTheme,
          primary_color: effectivePrimaryColor,
          secondary_color: effectiveSecondaryColor,
          button_radius: effectiveButtonRadius,
          font_family: effectiveFontFamily,
          layout_variant: effectiveLayoutVariant,
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
        estimated_prep_time: estimatedPrepTime.trim() || null,
      },
      public_settings: {
        ...menu.public_settings,
        logo_url: logoPreview ?? logoUrl ?? menu.public_settings?.logo_url,
        cover_image_url: coverMode === "image" ? coverPreview ?? coverImageUrl ?? menu.public_settings?.cover_image_url : null,
        cover_video_url: coverMode === "video" ? coverVideoUrl || menu.public_settings?.cover_video_url : null,
        theme,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        button_radius: buttonRadius,
        font_family: fontFamily,
        layout_variant: layoutVariant,
      },
    } as PublicMenuResponse;
  }, [menu, estimatedPrepTime, logoPreview, logoUrl, coverMode, coverPreview, coverImageUrl, coverVideoUrl, theme, primaryColor, secondaryColor, buttonRadius, fontFamily, layoutVariant]);

  useEffect(() => {
    const sendPreview = () => {
      if (!previewMenu) return;
      previewFrameRef.current?.contentWindow?.postMessage(
        { type: "storefront-preview:update", menu: previewMenu, theme },
        window.location.origin,
      );
    };
    const receive = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== previewFrameRef.current?.contentWindow) return;
      if (event.data?.type === "storefront-preview:ready") sendPreview();
      if (event.data?.type === "storefront-preview:theme" && ["white", "dark"].includes(event.data.theme)) setTheme(event.data.theme);
    };
    window.addEventListener("message", receive);
    sendPreview();
    return () => window.removeEventListener("message", receive);
  }, [previewMenu, theme]);

  const handleOpenPreview = () => {
    if (!tenantSlug) return;
    if (hasUnsavedChanges) {
      setToast({ type: "error", message: "Salve as alterações antes de abrir o cardápio publicado." });
      return;
    }
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
      setLogoError("Formato de arquivo não suportado.");
      return;
    }
    if (file.size > LOGO_MAX_SIZE_BYTES) {
      setLogoError("A logo excede o limite de 1 MB.");
      return;
    }

    let dimensions: { width: number; height: number };
    try {
      dimensions = await getImageDimensions(file);
    } catch {
      setLogoError("Não foi possível abrir a imagem. Escolha outra foto.");
      return;
    }
    const { width, height } = dimensions;
    const warnings: string[] = [];
    if (width < 400 || height < 400) warnings.push("Dimensão recomendada: 400×400px ou superior.");
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
      setCoverError("Formato de arquivo não suportado.");
      return;
    }
    if (file.size > COVER_IMAGE_MAX_SIZE_BYTES) {
      setCoverError("A imagem de capa excede o limite de 5 MB.");
      return;
    }

    let dimensions: { width: number; height: number };
    try {
      dimensions = await getImageDimensions(file);
    } catch {
      setCoverError("Não foi possível abrir a imagem. Escolha outra foto.");
      return;
    }
    const { width, height } = dimensions;
    const ratio = width / height;
    const warnings: string[] = [];
    if (width < 800 || height < 320) warnings.push("Dimensão mínima recomendada: 800×320px.");
    if (Math.abs(ratio - 2.5) > 0.2) warnings.push("Proporção ideal: 5:2.");
    setCoverWarning(warnings.join(" "));

    if (coverPreview) URL.revokeObjectURL(coverPreview);
    const nextPreview = URL.createObjectURL(file);
    setCoverPreview(nextPreview);
    setCoverImageFile(file);
    setCoverMode("image");
  };

  const onCoverVideoSelect = (file: File | null) => {
    if (!file) {
      setCoverVideoFile(null);
      setCoverVideoUrl("");
      return;
    }

    if (!validVideoTypes.includes(file.type)) {
      setToast({ type: "error", message: "Formato de arquivo não suportado." });
      setCoverVideoFile(null);
      return;
    }

    if (file.size > COVER_VIDEO_MAX_SIZE_BYTES) {
      setToast({ type: "error", message: "O vídeo de capa excede o limite de 20 MB." });
      setCoverVideoFile(null);
      return;
    }

    setToast(null);
    setCoverVideoFile(file);
    setCoverMode("video");
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

  if (isLoading) return <LoadingExperience label="Montando a prévia da loja" />;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  const fileInputClassName =
    "block w-full max-w-full min-w-0 text-sm text-slate-600 file:mr-3 file:min-h-11 file:rounded-xl file:border file:border-slate-200 file:bg-slate-50 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-100";

  const saveDisabled = isSaving || uploadingField !== null || Boolean(logoError || coverError) || !isHexColor(primaryColor) || !isHexColor(secondaryColor);

  const saveButton = (className = "") => (
    <Button className={`h-12 w-full rounded-xl text-sm font-bold ${className}`} onClick={handleSave} disabled={saveDisabled}>
      {isSaving || uploadingField ? "Salvando..." : "Salvar alterações"}
    </Button>
  );

  const switchMobileView = (view: "edit" | "preview") => {
    setMobileView(view);
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  return (
    <div className="min-w-0 pb-20 lg:flex lg:flex-row lg:overflow-hidden lg:pb-0">
      {toast ? (
        <div role="status" className={`fixed left-4 right-4 top-20 z-40 rounded-xl px-4 py-3 text-sm text-white shadow-lg lg:left-auto lg:right-5 lg:top-5 ${toast.type === "success" ? "bg-emerald-600" : "bg-red-600"}`}>
          {toast.message}
        </div>
      ) : null}

      <div className="sticky top-16 z-10 -mx-4 border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1" role="group" aria-label="Modo da prévia do cardápio">
          <button type="button" aria-pressed={mobileView === "edit"} onClick={() => switchMobileView("edit")} className={`flex min-h-11 items-center justify-center gap-2 rounded-lg text-sm font-semibold ${mobileView === "edit" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}><SlidersHorizontal className="h-4 w-4" />Editar {hasUnsavedChanges && <span className="h-2 w-2 rounded-full bg-brand-600" aria-label="Alterações não salvas" />}</button>
          <button type="button" aria-pressed={mobileView === "preview"} onClick={() => switchMobileView("preview")} className={`flex min-h-11 items-center justify-center gap-2 rounded-lg text-sm font-semibold ${mobileView === "preview" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}><Eye className="h-4 w-4" />Visualizar</button>
        </div>
      </div>

      <aside className={`${mobileView === "edit" ? "block" : "hidden"} min-w-0 w-full rounded-2xl border border-slate-200 bg-white lg:block lg:h-[calc(100vh-120px)] lg:w-[380px] lg:flex-shrink-0 lg:rounded-none lg:border-0 lg:border-r lg:border-black/10`}>
        <div className="space-y-4 px-4 py-5 lg:h-[calc(100%-78px)] lg:overflow-y-auto lg:px-5 lg:py-6">
          <div className="lg:hidden"><h1 className="text-lg font-bold text-slate-950">Personalize sua loja</h1><p className="mt-1 text-sm text-slate-600">Altere uma seção por vez e confira o resultado em Visualizar.</p></div>
          <Accordion title="Identidade" isOpen={openSections.identity} onToggle={() => setOpenSections((prev) => ({ ...prev, identity: !prev.identity }))}>
            <div className="space-y-2">
              <label htmlFor="storefront-logo" className="text-sm font-medium">Logo da loja</label>
              <input
                id="storefront-logo"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className={fileInputClassName}
                onChange={(event) => onLogoSelect(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-slate-500">400×400px recomendado • máximo 1 MB • PNG/JPG/WebP</p>
              {(logoPreview || logoUrl) ? (
                <div className={`w-fit rounded-xl border p-1 ${logoError ? "border-red-300" : "border-emerald-400"}`}>
                  <img src={logoPreview ?? logoUrl} alt="Preview do logo" className="h-16 w-16 rounded-full object-cover" />
                </div>
              ) : null}
              {(logoPreview || logoUrl) ? <Button variant="outline" onClick={() => onLogoSelect(null)}>Remover</Button> : null}
              {logoError ? <p className="text-xs text-red-600">{logoError}</p> : null}
              {logoWarning ? <p className="text-xs text-slate-600">{logoWarning}</p> : null}
            </div>

            <div className="space-y-2 pt-2">
              <label htmlFor="storefront-cover-image" className="text-sm font-medium">Imagem de capa</label>
              <input
                id="storefront-cover-image"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className={fileInputClassName}
                onChange={(event) => onCoverSelect(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-slate-500">1200×480px recomendado • proporção 5:2 • máximo 5 MB</p>
              {(coverPreview || coverImageUrl) ? (
                <div className={`w-fit rounded-md border p-1 ${coverError ? "border-red-300" : "border-emerald-400"}`}>
                  <img src={coverPreview ?? coverImageUrl} alt="Preview da capa" className="h-20 w-[200px] rounded object-cover" />
                </div>
              ) : null}
              <p className="text-xs text-slate-700">A parte inferior da capa fica coberta pelo nome da loja.</p>
              {(coverPreview || coverImageUrl) ? <Button variant="outline" onClick={() => onCoverSelect(null)}>Remover</Button> : null}
              {coverError ? <p className="text-xs text-red-600">{coverError}</p> : null}
              {coverWarning ? <p className="text-xs text-slate-600">{coverWarning}</p> : null}
            </div>

            <div className="space-y-2 pt-2">
              <label htmlFor="storefront-cover-video" className="text-sm font-medium">Capa em vídeo (opcional)</label>
              <input
                id="storefront-cover-video"
                type="file"
                accept="video/mp4,video/webm"
                className={fileInputClassName}
                onChange={(event) => onCoverVideoSelect(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-slate-500">MP4/WEBM • máximo 20 MB</p>
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
              <label htmlFor="storefront-prep-time" className="text-sm font-medium">Tempo estimado de preparo</label>
              <input id="storefront-prep-time" className="min-h-11 w-full rounded-xl border border-slate-200 px-3 py-2 text-base" value={estimatedPrepTime} onChange={(event) => setEstimatedPrepTime(event.target.value)} placeholder="Ex.: 35 min" />
            </div>
          </Accordion>

          <Accordion title="Cores e Tema" isOpen={openSections.colors} onToggle={() => setOpenSections((prev) => ({ ...prev, colors: !prev.colors }))}>
            <div className="space-y-2">
              <label className="text-sm font-medium">Tema</label>
              <div className="flex rounded-lg border border-slate-200 p-1">
                <button type="button" aria-pressed={theme === "white"} className={`min-h-11 flex-1 rounded-md px-3 py-2 text-sm ${theme === "white" ? "bg-slate-900 text-white" : "text-slate-700"}`} onClick={() => setTheme("white")}>Claro ☀</button>
                <button type="button" aria-pressed={theme === "dark"} className={`min-h-11 flex-1 rounded-md px-3 py-2 text-sm ${theme === "dark" ? "bg-slate-900 text-white" : "text-slate-700"}`} onClick={() => setTheme("dark")}>Escuro 🌙</button>
              </div>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Cor primária</label>
              <p className="text-xs text-slate-500">Usada em botões, destaques e CTAs</p>
              <div className="flex gap-2">
                <input type="color" aria-label="Escolher cor primária" value={isHexColor(primaryColor) ? primaryColor : DEFAULT_APPEARANCE.primary_color} onChange={(event) => setPrimaryColor(event.target.value)} className="h-11 w-14 shrink-0 rounded border border-slate-200" />
                <input aria-label="Código da cor primária" className="min-h-11 min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2 text-base" value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value)} />
              </div>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Cor secundária</label>
              <p className="text-xs text-slate-500">Usada em fundos e elementos de apoio</p>
              <div className="flex gap-2">
                <input type="color" aria-label="Escolher cor secundária" value={isHexColor(secondaryColor) ? secondaryColor : DEFAULT_APPEARANCE.secondary_color} onChange={(event) => setSecondaryColor(event.target.value)} className="h-11 w-14 shrink-0 rounded border border-slate-200" />
                <input aria-label="Código da cor secundária" className="min-h-11 min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2 text-base" value={secondaryColor} onChange={(event) => setSecondaryColor(event.target.value)} />
              </div>
            </div>
          </Accordion>

          <Accordion title="Tipografia e Layout" isOpen={openSections.typography} onToggle={() => setOpenSections((prev) => ({ ...prev, typography: !prev.typography }))}>
            <div className="space-y-2">
              <label className="text-sm font-medium">Fonte</label>
              <select className="min-h-11 w-full rounded-xl border border-slate-200 px-3 py-2 text-base" value={fontFamily} onChange={(event) => setFontFamily(event.target.value)} style={{ fontFamily }}>
                {fontOptions.map((font) => (
                  <option key={font} value={font} style={{ fontFamily: font }}>{font}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Raio do botão ({buttonRadius}px)</label>
              <input type="range" min={0} max={24} value={buttonRadius} onChange={(event) => setButtonRadius(Number(event.target.value))} className="min-h-11 w-full" />
              <button type="button" className="px-4 py-2 text-sm text-white" style={{ borderRadius: buttonRadius, background: primaryColor }}>Botão exemplo</button>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium">Layout</label>
              <select className="min-h-11 w-full rounded-xl border border-slate-200 px-3 py-2 text-base" value={layoutVariant} onChange={(event) => setLayoutVariant(event.target.value as AppearanceSettings["layout_variant"])}>
                <option value="clean">Clean</option>
                <option value="modern">Modern</option>
                <option value="commercial">Commercial</option>
              </select>
            </div>
          </Accordion>
        </div>

        <div className="hidden border-t border-black/10 bg-white px-5 py-4 lg:block">
          {saveButton()}
        </div>
      </aside>

      {mobileView === "edit" && <div className="fixed inset-x-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-3 shadow-[0_-8px_24px_rgba(15,23,42,0.06)] backdrop-blur lg:hidden [bottom:calc(68px+env(safe-area-inset-bottom))]">
        {saveButton()}
        {!isHexColor(primaryColor) || !isHexColor(secondaryColor) ? <p role="alert" className="mt-2 text-center text-xs text-red-600">Informe cores no formato #RRGGBB para salvar.</p> : null}
      </div>}

      <section className={`${mobileView === "preview" ? "block" : "hidden"} min-w-0 flex-1 pt-5 lg:block lg:px-8 lg:py-6`}>
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3">
          <div><p className="text-base font-bold text-slate-900">Como o cliente vê sua loja</p><p className="text-xs text-slate-500">As mudanças aparecem aqui antes de salvar.</p></div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg border border-slate-200 bg-white p-1" role="group" aria-label="Largura da prévia">
              <button type="button" onClick={() => setPreviewWidth(390)} aria-pressed={previewWidth === 390} className={`rounded-md px-3 py-1.5 text-xs font-medium ${previewWidth === 390 ? "bg-slate-900 text-white" : "text-slate-600"}`}>Celular</button>
              <button type="button" onClick={() => setPreviewWidth(520)} aria-pressed={previewWidth === 520} className={`rounded-md px-3 py-1.5 text-xs font-medium ${previewWidth === 520 ? "bg-slate-900 text-white" : "text-slate-600"}`}>Ampliada</button>
            </div>
            <span className="rounded-full border border-slate-200 px-2 py-1 text-xs text-slate-600">{theme === "dark" ? "Dark" : "White"}</span>
            <Button variant="outline" onClick={handleOpenPreview}>Abrir em nova aba</Button>
          </div>
        </div>

        <div className="mt-4 flex justify-center">
          <div className={`h-[min(860px,calc(100dvh-230px))] min-h-[480px] max-w-full overflow-hidden rounded-[24px] border border-black/10 bg-white shadow-[0_10px_30px_rgba(0,0,0,0.08)] lg:h-[min(860px,calc(100vh-150px))] lg:min-h-[600px] lg:rounded-[28px] ${previewWidth === 520 ? "w-full lg:w-[520px]" : "w-full lg:w-[390px]"}`}>
            <iframe ref={previewFrameRef} src="/storefront-preview-frame" title="Prévia interativa do cardápio" className="block h-full w-full border-0" />
          </div>
        </div>
        <p className="mt-3 text-center text-xs text-slate-500">A prévia usa a largura escolhida e mostra o cardápio como no celular.</p>
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
    <section className="rounded-xl border border-slate-200 p-3">
      <button type="button" aria-expanded={isOpen} onClick={onToggle} className="flex min-h-11 w-full items-center justify-between gap-3 text-left">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>
      {isOpen ? <div className="mt-3 space-y-3">{children}</div> : null}
    </section>
  );
}
