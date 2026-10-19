"use client";

import { paymentMethodLabel } from "@/lib/manualPayments";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { formatCurrencyFromCents } from "@/lib/currency";
import { type CachedTrackingOrder } from "@/lib/orderTrackingCache";
import { TRACKING_STEPS, TRACKING_STATUS_STEP, normalizeTrackingStatus, resolveTrackingStep } from "@/lib/orderTrackingStatus";
import { storefrontFetch } from "@/lib/storefrontApi";

export function OrderSummary({ order, onBack }: { order: CachedTrackingOrder; onBack: () => void }) {
  const [details, setDetails] = useState(order);
  const [status, setStatus] = useState(normalizeTrackingStatus(order.status || "pending"));
  const [unavailable, setUnavailable] = useState(false);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    setDetails(order);
    setStatus(normalizeTrackingStatus(order.status || "pending"));
    setUnavailable(false);
    setExpired(false);
    const refresh = async () => {
      let completed = false;
      try {
        const response = await storefrontFetch(
          `/public/order/${encodeURIComponent(order.token)}`,
          { cache: "no-store", signal: controller.signal }, order.tenant || undefined,
        );
        if (stopped) return;
        if (response.status === 404) {
          setExpired(true);
          return;
        }
        if (!response.ok) throw new Error("Pedido indisponível");
        const snapshot = await response.json();
        const raw = snapshot.status ?? snapshot.status_raw;
        if (typeof raw !== "string" || !raw.trim()) throw new Error("Status ausente");
        if (stopped) return;
        const nextStatus = normalizeTrackingStatus(raw);
        setStatus(nextStatus);
        setDetails((current) => ({
          ...current,
          orderNumber: snapshot.order_number ?? current.orderNumber,
          totalCents: snapshot.total_cents ?? current.totalCents,
          paymentMethod: snapshot.payment_method ?? current.paymentMethod,
          deliveryType: snapshot.order_type ?? current.deliveryType,
        }));
        setUnavailable(false);
        completed = nextStatus === "delivered" || nextStatus === "canceled";
      } catch {
        if (!stopped) setUnavailable(true);
      }
      if (!stopped && !completed) timer = setTimeout(refresh, 5000);
    };
    void refresh();
    return () => {
      stopped = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [order.token, order.tenant]);

  const step = resolveTrackingStep(status);
  return (
    <div className="space-y-4 rounded-2xl border border-emerald-100 bg-white p-5 text-slate-900 shadow-sm">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl text-emerald-600" aria-hidden="true">✓</div>
      <p className="text-center text-2xl italic">Pedido #{details.orderNumber || ""} recebido!</p>
      {expired ? <p role="status">Este acompanhamento expirou ou não está mais disponível.</p> : <>
        <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
          {details.subtotalCents != null && <div className="flex justify-between"><span>Subtotal</span><span>{formatCurrencyFromCents(details.subtotalCents)}</span></div>}
          {details.deliveryFeeCents != null && <div className="flex justify-between"><span>Taxa de entrega</span><span>{formatCurrencyFromCents(details.deliveryFeeCents)}</span></div>}
          {details.totalCents != null && <div className="flex justify-between"><span>Total</span><span>{formatCurrencyFromCents(details.totalCents)}</span></div>}
          <div className="flex justify-between"><span>Pagamento</span><span>{paymentMethodLabel(details.paymentMethod)}</span></div>
          <div className="flex justify-between"><span>Tipo</span><span>{details.deliveryType}</span></div>
          {(details.pointsEarned || 0) > 0 && <div className="text-emerald-700">+{details.pointsEarned} pontos ganhos</div>}
        </div>
        <div className="space-y-3 rounded-xl border border-slate-200 p-4">
          <p className="text-sm font-semibold">Acompanhar pedido</p>
          {unavailable && <p role="status" className="text-xs text-amber-700">Sem atualização recente. Tentando reconectar...</p>}
          {status === "canceled" ? <p role="status">Pedido cancelado</p> : TRACKING_STEPS.map((item) => {
            const current = item.key === status;
            const done = TRACKING_STATUS_STEP[item.key] < step;
            return <div key={item.key} className="flex items-center gap-2 text-sm">
              <span aria-hidden="true" className={`inline-block h-3 w-3 rounded-full border ${done || current ? "border-emerald-500 bg-emerald-500" : "border-slate-300"}`} />
              <span aria-current={current ? "step" : undefined} className={current ? "font-semibold text-emerald-700" : done ? "text-slate-900" : "text-slate-500"}>{item.label}</span>
              {current && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Status atual</span>}
            </div>;
          })}
        </div>
      </>}
      <Button className="w-full" onClick={onBack}>Voltar ao cardápio</Button>
    </div>
  );
}
