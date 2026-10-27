import { apiFetch } from "@/lib/api";

export type StorefrontAssetField = "logo" | "coverImage" | "coverVideo";

const assetNames: Record<StorefrontAssetField, string> = {
  logo: "logo",
  coverImage: "imagem de capa",
  coverVideo: "capa em vídeo",
};

export async function uploadStorefrontAsset(file: File, tenantId: number, field: StorefrontAssetField): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({ tenant_id: String(tenantId), category: "storefront", subfolder: field });
  const assetName = assetNames[field];

  let response: Response;
  try {
    response = await apiFetch(`/storefront/upload?${params.toString()}`, { method: "POST", body: formData });
  } catch {
    throw new Error(`Não foi possível enviar a ${assetName}. Verifique a conexão e tente novamente.`);
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = typeof payload?.detail === "string" ? payload.detail : null;
    if (response.status === 413 || response.status === 400) throw new Error(detail || `Arquivo da ${assetName} inválido.`);
    if (response.status === 404) throw new Error(`O envio da ${assetName} está indisponível. Atualize a página e tente novamente.`);
    if (response.status >= 500) throw new Error(`Não foi possível armazenar a ${assetName}. Tente novamente em instantes.`);
    throw new Error(detail || `Não foi possível enviar a ${assetName}.`);
  }

  const payload = await response.json().catch(() => null) as { url?: unknown } | null;
  if (typeof payload?.url !== "string" || !/^https?:\/\//.test(payload.url)) {
    throw new Error(`O envio da ${assetName} não retornou uma imagem válida.`);
  }
  return payload.url;
}
