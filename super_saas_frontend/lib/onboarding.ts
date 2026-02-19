import { api } from "@/lib/api";

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
  createTenant: (payload: OnboardingPayload) =>
    api.post<OnboardingResponse>("/api/onboarding/tenant", payload),
};
