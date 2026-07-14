import { sendDriverLocation } from "@/services/driverApi";

export type DriverLocationSample = {
  delivery_id: number;
  latitude: number;
  longitude: number;
  accuracy: number | null;
  speed: number | null;
  heading: number | null;
  recorded_at: string;
};

type Listener = (sample: DriverLocationSample) => void;
type ErrorListener = (message: string) => void;

type StartOptions = {
  deliveryId: number;
  onLocation?: Listener;
  onError?: ErrorListener;
};

class DriverLocationService {
  private watcherId: number | null = null;
  private activeDeliveryId: number | null = null;
  private queuedLatest: DriverLocationSample | null = null;

  isActive() {
    return this.watcherId !== null;
  }

  async requestPermission() {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      throw new Error("GPS indisponível neste navegador.");
    }
    if (navigator.permissions?.query) {
      const permission = await navigator.permissions.query({ name: "geolocation" as PermissionName });
      if (permission.state === "denied") throw new Error("Permissão de localização negada.");
    }
  }

  async getCurrentPosition() {
    await this.requestPermission();
    return new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
    });
  }

  start({ deliveryId, onLocation, onError }: StartOptions) {
    if (!deliveryId || !Number.isFinite(deliveryId)) {
      onError?.("Entrega ativa inválida para rastreamento.");
      return;
    }
    if (this.watcherId !== null) return;
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      onError?.("GPS indisponível neste navegador.");
      return;
    }
    this.activeDeliveryId = deliveryId;
    this.watcherId = navigator.geolocation.watchPosition(
      (position) => {
        if (this.activeDeliveryId !== deliveryId) return;
        const sample: DriverLocationSample = {
          delivery_id: deliveryId,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: Number.isFinite(position.coords.accuracy) ? position.coords.accuracy : null,
          speed: Number.isFinite(position.coords.speed) ? position.coords.speed : null,
          heading: Number.isFinite(position.coords.heading) ? position.coords.heading : null,
          recorded_at: new Date(position.timestamp || Date.now()).toISOString(),
        };
        onLocation?.(sample);
        sendDriverLocation(sample).then(() => { this.queuedLatest = null; }).catch(() => {
          this.queuedLatest = sample;
          onError?.("Sem conexão: a última posição será reenviada quando possível.");
        });
      },
      (error) => {
        onError?.(error.code === error.PERMISSION_DENIED ? "Permissão de localização negada." : "Não foi possível obter a localização atual.");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  }

  retryLatest() {
    if (!this.queuedLatest) return Promise.resolve(null);
    return sendDriverLocation(this.queuedLatest).then((result) => { this.queuedLatest = null; return result; });
  }

  stop() {
    if (this.watcherId !== null && typeof navigator !== "undefined" && navigator.geolocation) {
      navigator.geolocation.clearWatch(this.watcherId);
    }
    this.watcherId = null;
    this.activeDeliveryId = null;
    this.queuedLatest = null;
  }
}

export const driverLocationService = new DriverLocationService();
