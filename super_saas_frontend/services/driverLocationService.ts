import { getDriverAuthContext } from "@/lib/apiClient";
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

export type DriverLocationConnectionState = "connected" | "reconnecting" | "offline" | "rejected" | "tracking";

type Listener = (sample: DriverLocationSample) => void;
type ErrorListener = (message: string) => void;
type StateListener = (state: DriverLocationConnectionState, detail?: string) => void;

type StartOptions = { deliveryId: number; onLocation?: Listener; onError?: ErrorListener; onState?: StateListener };

const MIN_MOVING_INTERVAL_MS = 5000;
const MIN_STATIONARY_INTERVAL_MS = 20000;
const SIGNIFICANT_ACCURACY_GAIN_METERS = 10;
const MAX_RECONNECT_ATTEMPTS_BEFORE_HTTP_FALLBACK = 4;

function apiWsUrl(path: string) {
  const raw = process.env.NEXT_PUBLIC_API_URL || (typeof window !== "undefined" ? window.location.origin : "");
  const url = new URL(path, raw || "http://localhost");
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url;
}

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
  private activeDeliveryId: number | null = null;
  private queuedLatest: DriverLocationSample | null = null;
  private lastSent: DriverLocationSample | null = null;
  private lastSentAt = 0;
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private explicitStop = false;
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

  private connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) return;
    const { token, tenantId } = getDriverAuthContext();
    if (!token) { this.setState("offline", "Token do entregador ausente."); return; }
    const url = apiWsUrl("/ws/driver");
    url.searchParams.set("token", token.replace(/^Bearer\s+/i, ""));
    if (tenantId) url.searchParams.set("tenant_id", tenantId);
    this.socket = new WebSocket(url.toString());
    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.setState("connected");
      if (this.queuedLatest) this.sendViaSocket(this.queuedLatest);
    };
    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "driver_location_ack") { this.queuedLatest = null; this.setState("tracking"); }
        if (payload.type === "driver_location_rejected") { this.setState("rejected", payload.reason); this.options?.onError?.(`Localização rejeitada: ${payload.reason}`); }
      } catch { /* ignore malformed server message */ }
    };
    this.socket.onclose = () => { this.socket = null; if (!this.explicitStop) this.scheduleReconnect(); };
    this.socket.onerror = () => this.setState("offline", "Falha no WebSocket de localização.");
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectAttempts += 1;
    this.setState("reconnecting");
    const delay = Math.min(30000, 1000 * 2 ** (this.reconnectAttempts - 1));
    this.reconnectTimer = setTimeout(() => { this.reconnectTimer = null; this.connect(); this.maybeHttpFallback(); }, delay);
  }

  private shouldSend(sample: DriverLocationSample) {
    if (!this.lastSent) return true;
    const moved = distanceMeters(this.lastSent, sample);
    const errorMargin = Math.max(sample.accuracy ?? 0, this.lastSent.accuracy ?? 0);
    const accuracyGain = (this.lastSent.accuracy ?? Infinity) - (sample.accuracy ?? Infinity);
    if (accuracyGain >= SIGNIFICANT_ACCURACY_GAIN_METERS) return true;
    if (moved <= errorMargin) return false;
    const moving = (sample.speed ?? 0) > 0.5;
    return Date.now() - this.lastSentAt >= (moving ? MIN_MOVING_INTERVAL_MS : MIN_STATIONARY_INTERVAL_MS);
  }

  private sendViaSocket(sample: DriverLocationSample) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) { this.queuedLatest = sample; return false; }
    this.socket.send(JSON.stringify({ type: "driver_location_update", ...sample }));
    this.lastSent = sample;
    this.lastSentAt = Date.now();
    return true;
  }

  private maybeHttpFallback() {
    if (!this.queuedLatest || this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS_BEFORE_HTTP_FALLBACK) return;
    sendDriverLocation(this.queuedLatest).then(() => { this.queuedLatest = null; }).catch(() => this.setState("offline", "Fallback HTTP indisponível."));
  }

  start(options: StartOptions) {
    if (!options.deliveryId || !Number.isFinite(options.deliveryId)) { options.onError?.("Entrega ativa inválida para rastreamento."); return; }
    if (this.watcherId !== null) return;
    if (typeof navigator === "undefined" || !navigator.geolocation) { options.onError?.("GPS indisponível neste navegador."); return; }
    this.options = options;
    this.explicitStop = false;
    this.activeDeliveryId = options.deliveryId;
    this.connect();
    this.watcherId = navigator.geolocation.watchPosition((position) => {
      if (this.activeDeliveryId !== options.deliveryId) return;
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
      if (!this.shouldSend(sample)) return;
      if (!this.sendViaSocket(sample)) this.maybeHttpFallback();
    }, (error) => options.onError?.(error.code === error.PERMISSION_DENIED ? "Permissão de localização negada." : "Não foi possível obter a localização atual."),
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }

  retryLatest() { return this.queuedLatest ? sendDriverLocation(this.queuedLatest).then((result) => { this.queuedLatest = null; return result; }) : Promise.resolve(null); }

  stop() {
    this.explicitStop = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    if (this.socket) this.socket.close();
    this.socket = null;
    if (this.watcherId !== null && typeof navigator !== "undefined" && navigator.geolocation) navigator.geolocation.clearWatch(this.watcherId);
    this.watcherId = null;
    this.activeDeliveryId = null;
    this.queuedLatest = null;
    this.lastSent = null;
    this.options = null;
  }
}

export const driverLocationService = new DriverLocationService();

if (typeof window !== "undefined") {
  window.addEventListener("driver:session-cleared", () => driverLocationService.stop());
}
