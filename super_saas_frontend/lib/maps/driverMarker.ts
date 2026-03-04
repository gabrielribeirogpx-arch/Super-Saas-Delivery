import type { LngLatTuple, MapboxMap, MapboxMarker } from "./types";

function markerColorByStatus(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized === "ONLINE" || normalized === "DELIVERING") return "#16a34a";
  if (normalized === "BUSY") return "#f59e0b";
  return "#6b7280";
}

export class DriverMarker {
  private marker: MapboxMarker;
  private arrow: HTMLDivElement;

  constructor(map: MapboxMap, position: LngLatTuple, status: string) {
    if (!window.mapboxgl) {
      throw new Error("Mapbox indisponível para marcador.");
    }

    const element = document.createElement("div");
    element.style.width = "28px";
    element.style.height = "28px";
    element.style.borderRadius = "9999px";
    element.style.background = markerColorByStatus(status);
    element.style.border = "2px solid #fff";
    element.style.boxShadow = "0 0 0 2px rgba(15,23,42,0.25)";
    element.style.display = "flex";
    element.style.alignItems = "center";
    element.style.justifyContent = "center";

    this.arrow = document.createElement("div");
    this.arrow.style.width = "0";
    this.arrow.style.height = "0";
    this.arrow.style.borderLeft = "5px solid transparent";
    this.arrow.style.borderRight = "5px solid transparent";
    this.arrow.style.borderBottom = "10px solid #0f172a";
    this.arrow.style.transformOrigin = "50% 70%";
    element.appendChild(this.arrow);

    this.marker = new window.mapboxgl.Marker({ element }).setLngLat(position).addTo(map);
  }

  setPosition(position: LngLatTuple): void {
    this.marker.setLngLat(position);
  }

  getPosition(): { lng: number; lat: number } {
    return this.marker.getLngLat();
  }

  setHeading(degrees: number): void {
    this.arrow.style.transform = `rotate(${degrees}deg)`;
  }

  setStatus(status: string): void {
    this.marker.getElement().style.background = markerColorByStatus(status);
  }

  remove(): void {
    this.marker.remove();
  }
}
