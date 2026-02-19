import { api, apiFetch, ApiError } from "@/lib/api";

export interface OnboardingPayload {
  business_name: string;
  slug?: string;
  custom_domain?: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}

export interface OnboardingResponse {
  tenant_id: number;
  slug: string;
  tenant_slug?: string;
  admin_url?: string;
  custom_domain?: string | null;
  business_name: string;
  admin_email: string;
}

export interface AvailabilityResponse {
  slug?: string | null;
  slug_available?: boolean | null;
  custom_domain?: string | null;
  custom_domain_available?: boolean | null;
}

export const onboardingApi = {
  checkAvailability: (slug?: string, customDomain?: string) => {
    const params = new URLSearchParams();
    if (slug) params.set("slug", slug);
    if (customDomain) params.set("custom_domain", customDomain);
    const query = params.toString();
    return api.get<AvailabilityResponse>(`/api/onboarding/availability${query ? `?${query}` : ""}`);
  },
  createTenant: async (payload: OnboardingPayload) => {
    const response = await apiFetch("/api/onboarding/tenant", {
      method: "POST",
      body: payload,
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      const isJson = contentType.includes("application/json");
      const data = isJson ? await response.json() : await response.text();
      const message =
        typeof data === "string"
          ? data
          : (data as { detail?: string })?.detail || "Erro inesperado";
      throw new ApiError(message, response.status, data);
    }

    return response.json() as Promise<OnboardingResponse>;
  },
};
