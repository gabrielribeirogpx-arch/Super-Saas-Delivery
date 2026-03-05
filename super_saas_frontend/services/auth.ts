import { postApiDeliveryAuthLogin, type DeliveryLoginPayload } from "@/api/generated";

export async function loginDriver(payload: DeliveryLoginPayload) {
  const data = await postApiDeliveryAuthLogin(payload);
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
