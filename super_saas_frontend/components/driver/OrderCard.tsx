"use client";

import { useRef, useState } from "react";
import { ArrowRight, Banknote, Check, CreditCard, Loader2, MapPin, Navigation, Phone } from "lucide-react";
import { DriverOrder } from "@/services/driverApi";
import { DriverStatusBadge } from "@/components/driver/DriverUI";
import { paymentMethodLabel } from "@/lib/manualPayments";
import styles from "./Driver.module.css";

type Props = { order: DriverOrder; onAccept?: () => Promise<void> | void; onOpen?: () => void; offline?: boolean };
function money(cents?: number | null) { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format((cents || 0) / 100); }
function maskedPhone(phone?: string | null) { return phone ? phone.replace(/(\d{2})(\d+)(\d{4})/, "($1) •••••-$3") : "Telefone não informado"; }
export default function OrderCard({ order, onAccept, onOpen, offline }: Props) {
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState("");
  const acceptingRef = useRef(false);
  const hasCoords = Number.isFinite(order.destination_lat ?? order.customer_lat) && Number.isFinite(order.destination_lng ?? order.customer_lng);
  const accept = async () => {
    if (!onAccept || acceptingRef.current) return;
    if (!navigator.onLine) { setError("Conecte-se à internet para aceitar esta entrega."); return; }
    acceptingRef.current = true; setAccepting(true); setError("");
    try { await onAccept(); } catch { setError("Não foi possível confirmar a entrega. Atualize a lista e tente novamente; ela pode ter sido aceita por outra pessoa."); }
    finally { acceptingRef.current = false; setAccepting(false); }
  };
  return <article className={styles.orderCard}>
    <div className={styles.orderHeading}><div><p className={styles.eyebrow}>ENTREGA</p><h3>Pedido #{order.daily_order_number ?? order.id}</h3></div><DriverStatusBadge status={order.status} /></div>
    <div className={styles.customer}><span className={styles.customerAvatar}>{(order.customer_name || "C").trim().slice(0,1).toUpperCase()}</span><div><strong>{order.customer_name || "Cliente"}</strong><p><Phone size={13} aria-hidden="true" />{maskedPhone(order.phone)}</p></div></div>
    <div className={styles.destination}><MapPin size={20} aria-hidden="true" /><div><p className={styles.eyebrow}>DESTINO</p><strong>{order.address || "Endereço não informado"}</strong>{order.neighborhood && <p>{order.neighborhood}</p>}{order.reference && <p>Referência: {order.reference}</p>}</div></div>
    <div className={styles.orderInfo}><Info icon={<Banknote size={16} />} label="Total do pedido" value={order.total_cents == null ? "Não informado" : money(order.total_cents)} /><Info icon={<CreditCard size={16} />} label="Pagamento" value={paymentMethodLabel(order.payment_method)} /></div>
    <p className={styles.locationHint}><Navigation size={14} aria-hidden="true" />{hasCoords ? "Destino com coordenadas" : "Navegação pelo endereço"}</p>
    {error && <p role="alert" className={styles.alert}>{error}</p>}
    <div className={styles.cardActions}>{onOpen && <button type="button" onClick={onOpen} className={styles.secondaryButton}>Ver detalhes<ArrowRight size={16} aria-hidden="true" /></button>}{onAccept && <button type="button" onClick={accept} disabled={accepting || offline} className={styles.primaryButton}>{accepting ? <Loader2 size={18} className={styles.spinner} aria-hidden="true" /> : <Check size={18} aria-hidden="true" />}{accepting ? "Confirmando..." : "Aceitar entrega"}</button>}</div>
  </article>;
}
function Info({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div><p>{icon}{label}</p><strong>{value}</strong></div>; }
