import { ApiError } from "@/lib/api";
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

export type DriverLocationConnectionState = "reconnecting" | "offline" | "rejected" | "tracking";

type Listener = (sample: DriverLocationSample) => void;
type ErrorListener = (message: string) => void;
type StateListener = (state: DriverLocationConnectionState, detail?: string) => void;

type StartOptions = { deliveryId: number; onLocation?: Listener; onError?: ErrorListener; onState?: StateListener };

const MIN_MOVING_INTERVAL_MS = 5000;
const MIN_STATIONARY_INTERVAL_MS = 20000;
const SIGNIFICANT_ACCURACY_GAIN_METERS = 10;
const LOCATION_REQUEST_TIMEOUT_MS = 10000;
const RETRY_INTERVAL_MS = 5000;

function distanceMeters(a: DriverLocationSample, b: DriverLocationSample) {
  const toRad = (value: number) => (value * Math.PI) / 180;
  const earth = 6371000;
  const dLat = toRad(b.latitude - a.latitude);
  const dLng = toRad(b.longitude - a.longitude);
  const lat1 = toRad(a.latitude);
  const lat2 = toRad(b.latitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * earth * Math.asin(Math.sqrt(h));
}

class DriverLocationService {
  private watcherId: number | null = null;
  private queuedLatest: DriverLocationSample | null = null;
  private lastSent: DriverLocationSample | null = null;
  private lastSentAt = 0;
  private request: AbortController | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private retryAt = 0;
  private options: StartOptions | null = null;

  isActive() { return this.watcherId !== null; }

  async requestPermission() {
    if (typeof navigator === "undefined" || !navigator.geolocation) throw new Error("GPS indisponível neste navegador.");
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

  private setState(state: DriverLocationConnectionState, detail?: string) { this.options?.onState?.(state, detail); }

  private nextSendAt(sample: DriverLocationSample) {
    if (!this.lastSent) return 0;
    const moved = distanceMeters(this.lastSent, sample);
    const errorMargin = Math.max(sample.accuracy ?? 0, this.lastSent.accuracy ?? 0);
    const accuracyGain = (this.lastSent.accuracy ?? Infinity) - (sample.accuracy ?? Infinity);
    const moving = moved > Math.max(5, errorMargin) || (sample.speed ?? 0) > 0.5;
    return this.lastSentAt + (moving || accuracyGain >= SIGNIFICANT_ACCURACY_GAIN_METERS
      ? MIN_MOVING_INTERVAL_MS : MIN_STATIONARY_INTERVAL_MS);
  }

  private scheduleSend() {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    const sample = this.queuedLatest;
    if (!sample || this.request || !this.options) return;
    const due = Math.max(this.nextSendAt(sample), this.retryAt);
    if (due > Date.now()) {
      this.retryTimer = setTimeout(() => void this.flushLatest(), due - Date.now());
      return;
    }
    void this.flushLatest();
  }

  private async flushLatest() {
    this.retryTimer = null;
    const sample = this.queuedLatest;
    if (!sample || this.request || !this.options) return;
    const controller = new AbortController();
    this.request = controller;
    const timeout = setTimeout(() => controller.abort(), LOCATION_REQUEST_TIMEOUT_MS);
    try {
      await sendDriverLocation(sample, controller.signal);
      if (this.request !== controller) return;
      if (this.queuedLatest === sample) this.queuedLatest = null;
      this.lastSent = sample;
      this.lastSentAt = Date.now();
      this.retryAt = 0;
      this.setState("tracking");
    } catch (error) {
      if (this.request !== controller) return;
      this.retryAt = Date.now() + RETRY_INTERVAL_MS;
      if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) {
        if (this.queuedLatest === sample) this.queuedLatest = null;
        this.setState("rejected");
      } else {
        this.setState("offline", "Não foi possível enviar a localização. Tentando novamente.");
      }
    } finally {
      clearTimeout(timeout);
      if (this.request === controller) {
        this.request = null;
        this.scheduleSend();
      }
    }
  }

  start(options: StartOptions) {
    if (!options.deliveryId || !Number.isFinite(options.deliveryId)) { options.onError?.("Entrega ativa inválida para rastreamento."); return; }
    if (this.watcherId !== null) return;
    if (typeof navigator === "undefined" || !navigator.geolocation) { options.onError?.("GPS indisponível neste navegador."); return; }
    this.options = options;
    this.setState("reconnecting");
    this.watcherId = navigator.geolocation.watchPosition((position) => {
      if (this.options !== options) return;
      const sample: DriverLocationSample = {
        delivery_id: options.deliveryId,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: Number.isFinite(position.coords.accuracy) ? position.coords.accuracy : null,
        speed: Number.isFinite(position.coords.speed) ? position.coords.speed : null,
        heading: Number.isFinite(position.coords.heading) ? position.coords.heading : null,
        recorded_at: new Date(position.timestamp || Date.now()).toISOString(),
      };
      options.onLocation?.(sample);
      this.queuedLatest = sample;
      this.scheduleSend();
    }, (error) => options.onError?.(error.code === error.PERMISSION_DENIED ? "Permissão de localização negada." : "Não foi possível obter a localização atual."),
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }

  async retryLatest() {
    this.retryAt = 0;
    this.scheduleSend();
  }

  stop() {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.request?.abort();
    this.request = null;
    this.retryAt = 0;
    if (this.watcherId !== null && typeof navigator !== "undefined" && navigator.geolocation) navigator.geolocation.clearWatch(this.watcherId);
    this.watcherId = null;
    this.queuedLatest = null;
    this.lastSent = null;
    this.options = null;
  }
}

export const driverLocationService = new DriverLocationService();

if (typeof window !== "undefined") {
  window.addEventListener("driver:session-cleared", () => driverLocationService.stop());
}
