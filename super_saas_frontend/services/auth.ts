import { api } from "@/services/api";

type LoginPayload = {
  email: string;
  password: string;
};

type LoginResponse = {
  access_token?: string;
  token?: string;
};

export async function loginDriver(payload: LoginPayload) {
  const { data } = await api.post<LoginResponse>("/api/delivery/auth/login", payload);
  const token = data.access_token || data.token;

  if (!token) {
    throw new Error("Token de autenticação não retornado pelo backend.");
  }

  const bearerToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
  localStorage.setItem("driver_token", bearerToken);
  return bearerToken;
}

export function logoutDriver() {
  localStorage.removeItem("driver_token");
}
