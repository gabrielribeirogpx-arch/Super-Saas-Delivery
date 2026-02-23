import { PublicMenuResponse } from "@/components/storefront/types";
import { apiFetch, baseUrl } from "@/lib/api";

const parseMenuResponse = async (response: Response) => {
  if (!response.ok) {
    return null;
  }

  return (await response.json()) as PublicMenuResponse;
};

export async function fetchPublicMenuBySlug(slug: string) {
  const normalizedSlug = encodeURIComponent(slug);

  const attempts: Array<() => Promise<Response>> = [
    // rota pública principal por slug (via rewrite /api -> backend)
    () => apiFetch(`/api/public/${normalizedSlug}/menu`, { credentials: "include" }),
    // alguns proxies exigem barra final para casar a rota
    () => apiFetch(`/api/public/${normalizedSlug}/menu/`, { credentials: "include" }),
    // chamada direta ao backend (quando NEXT_PUBLIC_API_URL estiver configurado)
    () => apiFetch(`${baseUrl}/api/public/${normalizedSlug}/menu`, { credentials: "include" }),
    () => apiFetch(`${baseUrl}/api/public/${normalizedSlug}/menu/`, { credentials: "include" }),
    // fallback legado em instalações que expõem /public/menu com slug em query
    () => apiFetch(`/public/menu?slug=${normalizedSlug}`, { credentials: "include" }),
    () => apiFetch(`${baseUrl}/public/menu?slug=${normalizedSlug}`, { credentials: "include" }),
  ];

  let lastStatus: number | null = null;

  for (const attempt of attempts) {
    try {
      const response = await attempt();
      lastStatus = response.status;
      const parsed = await parseMenuResponse(response);
      if (parsed) {
        return parsed;
      }
    } catch {
      // Tenta o próximo endpoint para suportar diferentes topologias de deploy.
    }
  }

  throw new Error(
    lastStatus ? `Falha ao carregar cardápio (status ${lastStatus})` : "Falha ao carregar cardápio"
  );
}
