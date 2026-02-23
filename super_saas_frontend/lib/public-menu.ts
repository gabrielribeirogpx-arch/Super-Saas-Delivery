import { apiFetch, baseUrl } from "@/lib/api";

import { PublicMenuResponse } from "@/components/storefront/types";

const parseMenuResponse = async (response: Response) => {
  if (!response.ok) {
    return null;
  }

  return (await response.json()) as PublicMenuResponse;
};

export async function fetchPublicMenuBySlug(slug: string) {
  const normalizedSlug = encodeURIComponent(slug);

  const attempts: Array<() => Promise<Response>> = [
    () => apiFetch(`/api/public/${normalizedSlug}/menu`, { credentials: "include" }),
    () => apiFetch(`/api/public/${normalizedSlug}/menu/`, { credentials: "include" }),
    () => apiFetch(`/public/menu?slug=${normalizedSlug}`, { credentials: "include" }),
    () => apiFetch(`${baseUrl}/public/menu?slug=${normalizedSlug}`, { credentials: "include" }),
    () => apiFetch(`${baseUrl}/public/menu`, { credentials: "include" }),
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
