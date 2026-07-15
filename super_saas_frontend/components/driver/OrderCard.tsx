"use client";

import { useState } from "react";
import { ArrowRight, Banknote, Check, CreditCard, Loader2, MapPin, Navigation, Phone, UserRound } from "lucide-react";
import { DriverOrder } from "@/services/driverApi";
import { DriverStatusBadge } from "@/components/driver/DriverUI";

type Props = { order: DriverOrder; onAccept?: () => Promise<void> | void; onOpen?: () => void };

function money(cents?: number | null) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format((cents || 0) / 100);
}

function initials(name?: string) { return (name || "C").trim().slice(0, 1).toUpperCase(); }
function maskedPhone(phone?: string | null) { return phone ? phone.replace(/(\d{2})(\d+)(\d{4})/, "($1) •••••-$3") : "Telefone não informado"; }

export default function OrderCard({ order, onAccept, onOpen }: Props) {
  const [accepting, setAccepting] = useState(false);
  const hasCoords = Number.isFinite(order.destination_lat ?? order.customer_lat) && Number.isFinite(order.destination_lng ?? order.customer_lng);
  const accept = async () => { if (!onAccept || accepting) return; setAccepting(true); try { await onAccept(); } finally { setAccepting(false); } };
  return (
    <article className="mb-3 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm transition duration-200 active:scale-[.99] motion-safe:animate-[fadeIn_.25s_ease-out]">
      <div className="border-b border-slate-100 p-4">
        <div className="flex items-start justify-between gap-3"><div><p className="text-lg font-black text-slate-950">Pedido #{order.daily_order_number ?? order.id}</p><p className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-400">Prioridade normal</p></div><DriverStatusBadge status={order.status} /></div>
        <div className="mt-4 flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-slate-100 text-sm font-black text-slate-700">{initials(order.customer_name)}</div><div className="min-w-0"><p className="truncate font-bold text-slate-900">{order.customer_name}</p><p className="flex items-center gap-1 text-sm text-slate-500"><Phone className="h-3.5 w-3.5" />{maskedPhone(order.phone)}</p></div></div>
      </div>
      <div className="space-y-4 p-4">
        <div className="flex gap-3"><MapPin className="mt-1 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><p className="text-sm font-bold leading-5 text-slate-900">{order.address || "Endereço não informado"}</p>{order.neighborhood && <p className="text-sm text-slate-600">{order.neighborhood}</p>}{order.reference && <p className="text-xs font-semibold text-slate-500">Ref.: {order.reference}</p>}</div></div>
        <div className="grid grid-cols-2 gap-2 text-sm"><Info icon={<Banknote className="h-4 w-4" />} label="Valor" value={money(order.total_cents)} /><Info icon={<CreditCard className="h-4 w-4" />} label="Pagamento" value={order.payment_method || "--"} /><Info icon={<Navigation className="h-4 w-4" />} label="Distância" value={hasCoords ? "GPS disponível" : "Sem coordenadas"} /><Info icon={<UserRound className="h-4 w-4" />} label="Tipo" value={order.order_type || "Delivery"} /></div>
        <div className="grid grid-cols-1 gap-2 min-[360px]:grid-cols-2">{onOpen && <button onClick={onOpen} className="min-h-12 rounded-2xl border border-slate-300 px-4 text-sm font-black text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-500">Detalhes</button>}{onAccept && <button onClick={accept} disabled={accepting} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-4 text-sm font-black text-white shadow-lg shadow-emerald-200 transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-wait disabled:opacity-75">{accepting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Aceitar entrega<ArrowRight className="h-4 w-4" /></button>}</div>
      </div>
    </article>
  );
}
function Info({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div className="rounded-2xl bg-slate-50 p-3"><p className="flex items-center gap-1.5 text-xs font-bold text-slate-500">{icon}{label}</p><p className="mt-1 truncate text-sm font-black text-slate-900">{value}</p></div>; }
