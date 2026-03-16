export const GOOGLE_MAPS_SCRIPT_ID = "google-maps-js";
export const GOOGLE_MAPS_API_KEY = (process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || "").trim();

export function getGoogleMapsMissingKeyMessage(scope: string) {
  return `[${scope}] Google Maps API Key ausente. Injete a variável NEXT_PUBLIC_GOOGLE_MAPS_API_KEY no template de build/runtime.`;
}
