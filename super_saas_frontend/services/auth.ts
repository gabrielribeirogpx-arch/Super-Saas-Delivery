import { api } from "@/services/api";

type LoginPayload = {
  telefone: string;
  senha: string;
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

  localStorage.setItem("driver_token", token);
  return token;
}

export function logoutDriver() {
  localStorage.removeItem("driver_token");
}
