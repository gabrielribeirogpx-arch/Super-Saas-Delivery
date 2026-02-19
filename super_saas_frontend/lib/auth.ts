import { api } from "@/lib/api";

export interface AdminUser {
  id: number;
  tenant_id: number;
  email: string;
  name: string;
  role: string;
  active: boolean;
}

// Admin auth relies exclusively on HTTP-only cookie session (no JS token handling).
export type AdminLoginResponse = AdminUser;

export interface AdminLoginPayload {
  email: string;
  password: string;
}

export const authApi = {
  login: (payload: AdminLoginPayload, tenantSlug?: string) =>
    api.post<AdminLoginResponse>("/api/admin/auth/login", payload, tenantSlug ? { "x-tenant-slug": tenantSlug } : undefined),
  logout: () => api.post<{ ok: boolean }>("/api/admin/auth/logout"),
  me: () => api.get<AdminUser>("/api/admin/auth/me"),
};
