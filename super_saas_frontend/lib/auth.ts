import { api } from "@/lib/api";

export interface AdminUser {
  id: number;
  tenant_id: number;
  email: string;
  name: string;
  role: string;
  active: boolean;
}

export interface AdminLoginResponse extends AdminUser {
  access_token?: string;
  token_type?: "bearer";
}

export interface AdminLoginPayload {
  email: string;
  password: string;
}

export const authApi = {
  login: (payload: AdminLoginPayload) =>
    api.post<AdminLoginResponse>("/api/admin/auth/login", payload),
  logout: () => api.post<{ ok: boolean }>("/api/admin/auth/logout"),
  me: () => api.get<AdminUser>("/api/admin/auth/me"),
};
