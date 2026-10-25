"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import DeliveryMap from "@/components/driver/DeliveryMap";
import DriverAuthGuard from "@/components/driver/DriverAuthGuard";
import { acceptOrder, completeOrder, getDriverState, startOrder, DriverOrder } from "@/services/driverApi";
import { driverLocationService, type DriverLocationConnectionState } from "@/services/driverLocationService";
import { buildGoogleMapsUrl, buildTelUrl, buildWazeUrl, buildWhatsAppUrl } from "@/services/driverNavigation";
import styles from "@/components/driver/Driver.module.css";
import { ArrowLeft, ArrowUpRight, Check, CircleCheck, CreditCard, Loader2, MapPin, MessageCircle, Navigation, Package, Phone, Truck, WifiOff } from "lucide-react";
import { paymentMethodLabel } from "@/lib/manualPayments";
import { DriverBottomNav, DriverStatusBadge } from "@/components/driver/DriverUI";

type ToastType = "started" | "completed";

const NAV_STATE_STORAGE_KEY = "driver-active-navigation";

type PersistedNavigationState = {
  activeDeliveryId: number;
  status: string;
  navigationMode: boolean;
  driverLocation: { lat: number | null; lng: number | null };
  destination: { lat: number | null; lng: number | null; address: string | null };
  routeCoordinates: [number, number][];
  eta: string | null;
  distance: string | null;
};

export default function DriverDeliveryPage() {
  const params = useParams<{ orderId?: string; id?: string }>();
  const router = useRouter();
  const orderId = Number(params.orderId ?? params.id);
  const [orderDetails, setOrderDetails] = useState<DriverOrder | null>(null);
  const [status, setStatus] = useState("DRIVER_ASSIGNED");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [geoBlocked, setGeoBlocked] = useState(false);
  const [locationConnection, setLocationConnection] = useState<DriverLocationConnectionState>("offline");
  const [driverLat, setDriverLat] = useState<number | null>(null);
  const [driverLng, setDriverLng] = useState<number | null>(null);
  const [driverHeading, setDriverHeading] = useState<number | null>(null);
  const [driverSpeed, setDriverSpeed] = useState<number | null>(null);
  const [customerLat, setCustomerLat] = useState<number | null>(null);
  const [customerLng, setCustomerLng] = useState<number | null>(null);
  const [customerAddress, setCustomerAddress] = useState<string | null>(null);
  const [navigationMode, setNavigationMode] = useState(false);
  const [eta, setEta] = useState<string | null>(null);
  const [distance, setDistance] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastType | null>(null);
  const [completing, setCompleting] = useState(false);
  const [hideCard, setHideCard] = useState(false);
  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>([]);
  const [isMapInitialized, setIsMapInitialized] = useState(false);
  const [isFollowing, setIsFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [offline, setOffline] = useState(false);
  const [available, setAvailable] = useState(false);
  const [actionPending, setActionPending] = useState(false);
  const actionInFlight = useRef(false);
  const completedRef = useRef(false);
  const confirmDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    sync(); window.addEventListener("online", sync); window.addEventListener("offline", sync);
    return () => { window.removeEventListener("online", sync); window.removeEventListener("offline", sync); };
  }, []);

  const persistNavigationState = (nextState: PersistedNavigationState) => {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.setItem(NAV_STATE_STORAGE_KEY, JSON.stringify(nextState));
  };

  useEffect(() => {
    setOrderDetails(null); setLoading(true); setLoadError(""); setAvailable(false); completedRef.current = false;
    setCustomerLat(null);
    setCustomerLng(null);
    setCustomerAddress(null);
    setStatus("DRIVER_ASSIGNED");
    setNavigationMode(false);
    driverLocationService.stop();
    setCompleting(false);
    setHideCard(false);
    setEta(null);
    setDistance(null);
    setRouteCoordinates([]);
    setIsMapInitialized(false);
    setIsFollowing(false);
  }, [orderId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const raw = localStorage.getItem(NAV_STATE_STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      const parsed = JSON.parse(raw) as PersistedNavigationState;
      if (parsed.activeDeliveryId !== orderId) {
        return;
      }

      setStatus(parsed.status);
      setNavigationMode(parsed.navigationMode);
      setDriverLat(parsed.driverLocation.lat);
      setDriverLng(parsed.driverLocation.lng);
      setCustomerLat(parsed.destination.lat);
      setCustomerLng(parsed.destination.lng);
      setCustomerAddress(parsed.destination.address);
      setRouteCoordinates(parsed.routeCoordinates ?? []);
      setEta(parsed.eta);
      setDistance(parsed.distance);
      setIsFollowing(parsed.navigationMode);
    } catch {
      localStorage.removeItem(NAV_STATE_STORAGE_KEY);
    }
  }, [orderId]);

  useEffect(() => {
    persistNavigationState({
      activeDeliveryId: orderId,
      status,
      navigationMode,
      driverLocation: { lat: driverLat, lng: driverLng },
      destination: { lat: customerLat, lng: customerLng, address: customerAddress },
      routeCoordinates,
      eta,
      distance,
    });
  }, [orderId, status, navigationMode, driverLat, driverLng, customerLat, customerLng, customerAddress, routeCoordinates, eta, distance]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const state = await getDriverState();
        if (stopped || completedRef.current) return;
        const assigned = state.active_delivery?.id === orderId ? state.active_delivery : state.assigned_orders?.find(order => order.id === orderId);
        const offered = state.available_orders?.find(order => order.id === orderId);
        const order = assigned ?? offered;
        if (order) {
          setStatus(order.status); setOrderDetails(order); setAvailable(!assigned && Boolean(offered));
          setCustomerLat(order.customer_lat ?? order.destination_lat ?? null);
          setCustomerLng(order.customer_lng ?? order.destination_lng ?? null);
          setCustomerAddress(order.address ?? null);
        } else {
          setOrderDetails(null); setAvailable(false);
          if (!navigationMode) { setCustomerLat(null); setCustomerLng(null); setCustomerAddress(null); }
        }
        setLoadError("");
      } catch { if (!stopped) setLoadError("Não foi possível atualizar esta entrega. Confira sua conexão."); }
      finally { if (!stopped) { setLoading(false); if (!completedRef.current) timer = setTimeout(refresh, 4000); } }
    };
    void refresh();
    return () => { stopped = true; clearTimeout(timer); };
  }, [orderId, navigationMode]);

  useEffect(() => {
    if (!navigationMode || status === "DELIVERED") {
      driverLocationService.stop();
      return;
    }

    driverLocationService.start({
      deliveryId: orderId,
      onState: (state) => setLocationConnection(state),
      onLocation: (sample) => {
        setDriverLat(sample.latitude);
        setDriverLng(sample.longitude);
        setDriverHeading(sample.heading);
        setDriverSpeed(sample.speed);
        setFeedback(null);
      },
      onError: (message) => {
        setGeoBlocked(message.toLowerCase().includes("negada"));
        setFeedback(message);
      },
    });

    return () => {
      driverLocationService.stop();
    };
  }, [navigationMode, orderId, status]);

  const runAction = async (action: () => Promise<void>) => {
    if (actionInFlight.current) return;
    if (!navigator.onLine) { setFeedback("Sem conexão. Aguarde a internet voltar para confirmar esta ação."); return; }
    actionInFlight.current = true; setActionPending(true); setFeedback(null);
    try { await action(); }
    catch { setFeedback("A ação não foi confirmada. Confira o status da entrega antes de tentar novamente."); }
    finally { actionInFlight.current = false; setActionPending(false); }
  };

  const handleAccept = () => runAction(async () => {
    const result = await acceptOrder(orderId);
    if (result === undefined) throw new Error("Sem confirmação");
    setAvailable(false); setStatus("DRIVER_ASSIGNED");
  });

  const handleStart = () => runAction(async () => {
    let position: GeolocationPosition;
    try { position = await driverLocationService.getCurrentPosition(); }
    catch { setGeoBlocked(true); setFeedback("Permita o acesso à localização para iniciar a entrega. Confira as permissões do navegador."); return; }
    setGeoBlocked(false); setDriverLat(position.coords.latitude); setDriverLng(position.coords.longitude);
    const result = await startOrder(orderId);
    if (result === undefined) throw new Error("Sem confirmação");
    setStatus("OUT_FOR_DELIVERY"); setNavigationMode(true); setIsFollowing(true); setToast("started");
  });

  const handleComplete = () => runAction(async () => {
    const result = await completeOrder(orderId);
    if (result === undefined) throw new Error("Sem confirmação");
    completedRef.current = true;
    setStatus("DELIVERED"); setNavigationMode(false); setIsFollowing(false); setCompleting(true); setToast("completed");
    localStorage.removeItem(NAV_STATE_STORAGE_KEY);
    setTimeout(() => setHideCard(true), 700);
    setTimeout(() => router.push("/driver/dashboard"), 1350);
  });

  const moving = ["OUT_FOR_DELIVERY", "IN_TRANSIT", "PICKED_UP", "ARRIVED"].includes(status);
  const canStart = !available && ["DRIVER_ASSIGNED", "ACCEPTED"].includes(status);
  const hasDestination = Boolean(customerAddress) || (Number.isFinite(customerLat) && Number.isFinite(customerLng));
  const money = (cents: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);

  return (
    <DriverAuthGuard>
      <main className={styles.routePage}>
      <DeliveryMap
        orderId={orderId}
        driverLat={driverLat}
        driverLng={driverLng}
        driverHeading={driverHeading}
        driverSpeed={driverSpeed}
        customerLat={customerLat}
        customerLng={customerLng}
        customerAddress={customerAddress}
        navigationMode={navigationMode}
        initialRouteCoordinates={routeCoordinates}
        onRouteChange={(coordinates) => {
          if (coordinates.length === 0) {
            return;
          }

          setRouteCoordinates((prev) => {
            const prevFirst = prev[0];
            const nextFirst = coordinates[0];
            const prevLast = prev.at(-1);
            const nextLast = coordinates.at(-1);
            const unchanged =
              prev.length === coordinates.length &&
              prevFirst?.[0] === nextFirst?.[0] &&
              prevFirst?.[1] === nextFirst?.[1] &&
              prevLast?.[0] === nextLast?.[0] &&
              prevLast?.[1] === nextLast?.[1];

            return unchanged ? prev : coordinates;
          });
        }}
        onMapReadyChange={(ready) => {
          setIsMapInitialized(ready);
        }}
        onRecenter={() => {
          setNavigationMode(true);
          setIsFollowing(true);
        }}
        onOverview={() => {
          setNavigationMode(false);
          setIsFollowing(false);
        }}
        onFollowModeChange={(next) => {
          setIsFollowing(next);
          if (next) {
            setNavigationMode(true);
          }
        }}
        onMetricsChange={({ eta: currentEta, distance: currentDistance }) => {
          setEta((prev) => (prev === currentEta ? prev : currentEta));
          setDistance((prev) => (prev === currentDistance ? prev : currentDistance));
        }}
      />

      {!isMapInitialized && <div className={styles.mapFallback}><MapPin size={24} aria-hidden="true" /><p>Rota da entrega</p><span>Abra Google Maps ou Waze nos detalhes para navegar.</span></div>}
      <header className={styles.routeHeader}>
        <button type="button" onClick={() => router.push("/driver/dashboard")} aria-label="Voltar ao painel"><ArrowLeft size={20} aria-hidden="true" /></button>
        <div><p className={styles.eyebrow}>SUA ENTREGA</p><h1>Pedido #{orderDetails?.daily_order_number ?? orderId}</h1></div>
        {orderDetails && <DriverStatusBadge status={status} />}
      </header>

      {!hideCard && <section className={styles.deliveryPanel} aria-label="Detalhes da entrega">
        <div className={styles.panelHandle} aria-hidden="true" />
        <div className={styles.panelContent}>
          {loading && <p className={styles.notice} role="status">Carregando entrega...</p>}
          {loadError && <p className={styles.alert} role="alert">{loadError}</p>}
          {!loading && !orderDetails && !loadError && <p className={styles.notice} role="status">Esta entrega não está disponível para sua conta. Volte ao painel para conferir a lista atualizada.</p>}
          {offline && <p role="status" className={styles.notice}><WifiOff size={16} aria-hidden="true" /> Sem conexão. Aguarde para confirmar ações.</p>}
          {orderDetails && <>
            <div className={styles.routeMetrics}><div><span>Tempo estimado</span><strong>{eta || (isMapInitialized ? "A calcular" : "Não disponível")}</strong></div><div><span>Distância da rota</span><strong>{distance || (isMapInitialized ? "A calcular" : "Não disponível")}</strong></div></div>
            <div className={styles.deliveryCustomer}><span className={styles.customerAvatar}>{(orderDetails.customer_name || "C").slice(0,1).toUpperCase()}</span><div><p className={styles.eyebrow}>CLIENTE</p><h2>{orderDetails.customer_name || "Cliente"}</h2></div></div>
            <div className={styles.destination}><MapPin size={20} aria-hidden="true" /><div><p className={styles.eyebrow}>ENDEREÇO DE ENTREGA</p><strong>{customerAddress || "Endereço não informado"}</strong>{orderDetails.complement && <p>Complemento: {orderDetails.complement}</p>}{orderDetails.reference && <p>Referência: {orderDetails.reference}</p>}</div></div>
            {orderDetails.notes && <p className={styles.notice}>Observações: {orderDetails.notes}</p>}
            <div className={styles.navigationLinks}>
              {hasDestination ? <><a target="_blank" rel="noopener noreferrer" href={buildGoogleMapsUrl({ latitude: customerLat, longitude: customerLng, address: customerAddress })}><Navigation size={17} aria-hidden="true" />Google Maps<ArrowUpRight size={14} aria-hidden="true" /></a><a target="_blank" rel="noopener noreferrer" href={buildWazeUrl({ latitude: customerLat, longitude: customerLng, address: customerAddress })}><MapPin size={17} aria-hidden="true" />Waze<ArrowUpRight size={14} aria-hidden="true" /></a></> : <p className={styles.notice}>A loja precisa informar o endereço para abrir a navegação.</p>}
            </div>
            <div className={styles.contactLinks}>
              {buildTelUrl(orderDetails.phone) ? <a href={buildTelUrl(orderDetails.phone)!}><Phone size={17} aria-hidden="true" />Ligar para cliente</a> : <span>Telefone não informado</span>}
              {buildWhatsAppUrl(orderDetails.phone) && <a target="_blank" rel="noopener noreferrer" href={buildWhatsAppUrl(orderDetails.phone)!}><MessageCircle size={17} aria-hidden="true" />WhatsApp</a>}
            </div>
            <div className={styles.paymentInfo}><CreditCard size={19} aria-hidden="true" /><div><span>Forma de pagamento</span><strong>{paymentMethodLabel(orderDetails.payment_method)}</strong>{orderDetails.change_for && <p>Troco para {orderDetails.change_for}</p>}</div>{orderDetails.total_cents != null && <b>{money(orderDetails.total_cents)}</b>}</div>
            {orderDetails.items && <details className={styles.itemsDisclosure}><summary><Package size={17} aria-hidden="true" />Itens do pedido</summary><p>{orderDetails.items}</p></details>}
            {navigationMode && <p role="status" className={styles.notice}>{locationConnection === "tracking" ? "Localização enviada à loja." : locationConnection === "rejected" ? "Localização não aceita. Confira a entrega atribuída." : "Aguardando conexão e envio da localização."} Mantenha esta tela aberta durante a entrega.</p>}
            <details className={styles.help}><summary>Precisa de ajuda?</summary><p>Em caso de atraso, endereço incorreto ou dificuldade na entrega, fale com a loja pelo canal combinado para receber orientações.</p></details>
          </>}
          {feedback && <p role="alert" className={styles.alert}>{feedback}</p>}
          {geoBlocked && <p className={styles.notice}>O GPS está bloqueado. Libere a localização nas configurações do navegador.</p>}
        </div>
        {orderDetails && <div className={styles.deliveryActions}>
          {available && <><p>Ao aceitar, esta entrega será vinculada a você.</p><button type="button" className={styles.primaryButton} disabled={actionPending || offline} onClick={handleAccept}>{actionPending ? <Loader2 size={18} className={styles.spinner} aria-hidden="true" /> : <Check size={18} aria-hidden="true" />}Aceitar entrega</button></>}
          {canStart && <><p>Retire o pedido na loja antes de iniciar.</p><button type="button" className={styles.primaryButton} disabled={actionPending || offline} onClick={handleStart}>{actionPending ? <Loader2 size={18} className={styles.spinner} aria-hidden="true" /> : <Truck size={18} aria-hidden="true" />}{actionPending ? "Confirmando..." : "Iniciar entrega"}</button></>}
          {moving && <><p>Confirme somente após entregar ao cliente.</p><button type="button" className={styles.successButton} disabled={actionPending || offline} onClick={() => confirmDialog.current?.showModal()}><CircleCheck size={18} aria-hidden="true" />Marcar como entregue</button></>}
          {status === "DELIVERED" && <p role="status" className={styles.completed}><CircleCheck size={22} aria-hidden="true" />Entrega concluída</p>}
        </div>}
      </section>}
      <dialog ref={confirmDialog} className={styles.confirmDialog} aria-labelledby="driver-complete-title">
        <div className={styles.confirmIcon}><Package size={26} aria-hidden="true" /></div><h2 id="driver-complete-title">Pedido entregue ao cliente?</h2><p>Confirme apenas se a entrega já foi realizada. O status será atualizado após a resposta da loja.</p><div><button type="button" className={styles.secondaryButton} onClick={() => confirmDialog.current?.close()}>Ainda não</button><button type="button" className={styles.successButton} disabled={actionPending} onClick={() => { confirmDialog.current?.close(); void handleComplete(); }}>Sim, foi entregue</button></div>
      </dialog>
      {toast && <div role="status" className={styles.toast}>{toast === "started" ? "Entrega iniciada. Boa rota!" : "Entrega concluída."}</div>}
      <DriverBottomNav active="route" hasRoute={!available && Boolean(orderDetails) && status !== "DELIVERED"} routeId={orderId} />
      </main>
    </DriverAuthGuard>
  );
}
