"use client";

import { useMemo, useState } from "react";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";
import { Button } from "@/components/ui/button";

export type StripeCheckout = { client_secret: string; publishable_key: string; plan_code: string; price_cents: number };

function PaymentForm({ onClose }: { onClose: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function pay() {
    if (!stripe || !elements || busy) return;
    setBusy(true); setError("");
    const result = await stripe.confirmPayment({ elements,
      confirmParams: { return_url: window.location.origin + "/subscriptions?stripe_return=1" },
      redirect: "if_required" });
    if (result.error) {
      setError(result.error.message || "Não foi possível confirmar o pagamento.");
      setBusy(false);
    } else {
      window.location.assign("/subscriptions?stripe_return=1");
    }
  }
  return <div className="space-y-4">
    <PaymentElement />
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    <div className="flex flex-wrap gap-3"><Button disabled={!stripe || busy} onClick={() => void pay()}>{busy ? "Confirmando..." : "Confirmar assinatura"}</Button>
      <Button variant="outline" disabled={busy} onClick={onClose}>Voltar</Button></div>
    <p className="text-xs text-slate-600">Seu acesso será liberado após a confirmação do pagamento pela Stripe.</p>
  </div>;
}

export function StripePayment({ checkout, onClose }: { checkout: StripeCheckout; onClose: () => void }) {
  const stripe = useMemo(() => loadStripe(checkout.publishable_key), [checkout.publishable_key]);
  return <section className="space-y-4 rounded-xl border bg-white p-6" aria-label="Pagamento seguro">
    <h2 className="text-lg font-semibold">Pagamento seguro</h2>
    <p className="text-sm text-slate-600">Assinatura mensal de {(checkout.price_cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}.</p>
    <Elements stripe={stripe} options={{ clientSecret: checkout.client_secret, locale: "pt-BR" }}>
      <PaymentForm onClose={onClose} />
    </Elements>
  </section>;
}
