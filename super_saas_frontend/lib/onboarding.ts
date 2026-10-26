import { api, apiFetch, ApiError } from "@/lib/api";

export interface OnboardingPayload {
  plan_code?: string;
  captcha_token?: string;
  accept_terms?: boolean;
  terms_version?: string;
  business_name: string;
  slug?: string;
  custom_domain?: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}

export interface OnboardingResponse {
  checkout_url?: string | null;
  subscription_required?: boolean;
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
  createTenant: async (payload: OnboardingPayload, invitation?: string) => {
    const response = await apiFetch("/api/onboarding/tenant", {
      method: "POST",
      headers: invitation ? { "X-Onboarding-Invite": invitation } : undefined,
      body: payload,
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      const isJson = contentType.includes("application/json");
      const data = isJson ? await response.json() : await response.text();
      const detail = typeof data === "object" && data !== null ? (data as { detail?: unknown }).detail : undefined;
      const message = typeof detail === "string" ? detail : response.status === 422
        ? "Confira os dados do cadastro e tente novamente."
        : "Não foi possível confirmar seu cadastro. Se já criou sua loja, use Entrar para retomar a contratação.";
      throw new ApiError(message, response.status, data);
    }

    return response.json() as Promise<OnboardingResponse>;
  },
};
