export type Coordinates = { latitude?: number | null; longitude?: number | null; address?: string | null };

function hasValidCoordinates(target: Coordinates) {
  return Number.isFinite(target.latitude) && Number.isFinite(target.longitude);
}

export function buildGoogleMapsUrl(target: Coordinates) {
  const destination = hasValidCoordinates(target)
    ? `${target.latitude},${target.longitude}`
    : encodeURIComponent(target.address || "");
  return `https://www.google.com/maps/dir/?api=1&destination=${destination}`;
}

export function buildWazeUrl(target: Coordinates) {
  if (hasValidCoordinates(target)) {
    return `https://waze.com/ul?ll=${target.latitude},${target.longitude}&navigate=yes`;
  }
  return `https://waze.com/ul?q=${encodeURIComponent(target.address || "")}&navigate=yes`;
}

export function normalizePhone(phone?: string | null) {
  const digits = String(phone || "").replace(/\D/g, "");
  if (digits.length < 10 || digits.length > 13) return null;
  return digits.startsWith("55") ? digits : `55${digits}`;
}

export function buildTelUrl(phone?: string | null) {
  const normalized = normalizePhone(phone);
  return normalized ? `tel:+${normalized}` : null;
}

export function buildWhatsAppUrl(phone?: string | null) {
  const normalized = normalizePhone(phone);
  return normalized ? `https://wa.me/${normalized}` : null;
}
