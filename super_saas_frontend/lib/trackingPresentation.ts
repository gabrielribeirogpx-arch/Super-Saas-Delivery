export function isFiniteTrackingNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatTrackingEta(durationSeconds?: number | null, distanceMeters?: number | null) {
  const parts: string[] = [];
  if (isFiniteTrackingNumber(durationSeconds) && durationSeconds > 0) {
    parts.push(`Chegando em ${Math.max(1, Math.round(durationSeconds / 60))} min`);
  }
  if (isFiniteTrackingNumber(distanceMeters) && distanceMeters > 0) {
    const kilometers = distanceMeters / 1000;
    parts.push(`${kilometers.toFixed(kilometers >= 10 ? 0 : 1)} km`);
  }
  return parts.length ? parts.join(" • ") : null;
}
