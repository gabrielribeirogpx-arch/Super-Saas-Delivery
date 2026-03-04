import type { LngLatTuple, MapboxMap, MapboxMarker } from "@/lib/maps/types";

function markerColorByStatus(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized === "ONLINE" || normalized === "DELIVERING") return "#22c55e";
  if (normalized === "BUSY") return "#f59e0b";
  return "#6b7280";
}

export class DriverMarker {
  private marker: MapboxMarker;
  private pulse: HTMLDivElement;
  private core: HTMLDivElement;

  constructor(map: MapboxMap, position: LngLatTuple, status: string) {
    if (!window.mapboxgl) {
      throw new Error("Mapbox indisponível para marcador.");
    }

    const element = document.createElement("div");
    element.style.width = "20px";
    element.style.height = "20px";
    element.style.position = "relative";

    this.pulse = document.createElement("div");
    this.pulse.style.position = "absolute";
    this.pulse.style.inset = "0";
    this.pulse.style.borderRadius = "50%";
    this.pulse.style.background = markerColorByStatus(status);
    this.pulse.style.boxShadow = "0 0 0 5px rgba(34,197,94,0.25), 0 0 20px rgba(34,197,94,0.8)";
    this.pulse.style.opacity = "0.9";

    this.core = document.createElement("div");
    this.core.style.position = "absolute";
    this.core.style.inset = "0";
    this.core.style.borderRadius = "50%";
    this.core.style.background = markerColorByStatus(status);
    this.core.style.boxShadow = "0 12px 24px rgba(0,0,0,0.45)";
    this.core.style.transition = "transform 300ms ease-out";

    element.appendChild(this.pulse);
    element.appendChild(this.core);

    this.marker = new window.mapboxgl.Marker({ element }).setLngLat(position).addTo(map);
  }

  setPosition(position: LngLatTuple): void {
    this.marker.setLngLat(position);
  }

  getPosition(): { lng: number; lat: number } {
    return this.marker.getLngLat();
  }

  setHeading(degrees: number): void {
    this.core.style.transform = `rotate(${degrees}deg)`;
  }

  setStatus(status: string): void {
    const color = markerColorByStatus(status);
    this.core.style.background = color;
    this.pulse.style.background = color;
  }

  remove(): void {
    this.marker.remove();
  }
}
