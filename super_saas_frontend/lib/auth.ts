import { api } from "@/lib/api";

export interface AdminUser {
  id: number;
  tenant_id: number;
  email: string;
  name: string;
  role: string;
  active: boolean;
}

export interface AdminLoginPayload {
  tenant_id: number;
  email: string;
  password: string;
}

export const authApi = {
  login: (payload: AdminLoginPayload) =>
    api.post<AdminUser>("/api/admin/auth/login", payload),
  logout: () => api.post<{ ok: boolean }>("/api/admin/auth/logout"),
  me: () => api.get<AdminUser>("/api/admin/auth/me"),
};
