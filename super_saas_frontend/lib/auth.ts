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
  access_token: string;
  token_type: "bearer";
}

export interface AdminLoginPayload {
  tenant_id: number;
  email: string;
  password: string;
}

export const ADMIN_ACCESS_TOKEN_KEY = "admin_access_token";
export const ADMIN_TENANT_ID_KEY = "admin_tenant_id";
export const ADMIN_EMAIL_KEY = "admin_email";

export const getAdminAccessToken = () => {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ADMIN_ACCESS_TOKEN_KEY);
};

export const storeAdminSession = (data: AdminLoginResponse) => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ADMIN_ACCESS_TOKEN_KEY, data.access_token);
  window.localStorage.setItem(ADMIN_TENANT_ID_KEY, String(data.tenant_id));
  window.localStorage.setItem(ADMIN_EMAIL_KEY, data.email);
};

export const clearAdminSession = () => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(ADMIN_ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(ADMIN_TENANT_ID_KEY);
  window.localStorage.removeItem(ADMIN_EMAIL_KEY);
};

export const authApi = {
  login: (payload: AdminLoginPayload) =>
    api.post<AdminLoginResponse>("/api/admin/auth/login", payload),
  logout: () => api.post<{ ok: boolean }>("/api/admin/auth/logout"),
  me: () => api.get<AdminUser>("/api/admin/auth/me"),
};
