"use client";

export default function DeliveryMap({ lat, lng }: { lat?: number; lng?: number }) {
  return (
    <div className="rounded-lg border p-3 text-sm">
      <p className="font-medium">Map</p>
      <p>Driver: {lat ?? "-"}, {lng ?? "-"}</p>
      <p className="text-gray-500">Integrate Google Maps or Mapbox token to render route.</p>
    </div>
  );
}
