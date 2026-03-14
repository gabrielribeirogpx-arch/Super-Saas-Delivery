"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { buildStorefrontApiUrl } from "@/lib/storefrontApi";

type CheckoutStep = "cart" | "identify" | "new-customer" | "returning" | "payment" | "submitting" | "success";

interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  cartItems: Array<{
    id: string | number;
    name: string;
    price: number;
    quantity: number;
    modifiers?: string[];
    selected_modifiers?: Array<{ group_id: number; option_id: number; name: string; price_cents: number }>;
  }>;
  onOrderSuccess: () => void;
  tenant: {
    slug: string;
    store_id: number;
    name: string;
  };
  theme?: "dark" | "white";
}

export function CheckoutModal({ isOpen, onClose, cartItems, onOrderSuccess, tenant, theme = "white" }: CheckoutModalProps) {
  const [checkoutStep, setCheckoutStep] = useState<CheckoutStep>("cart");
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("pix");
  const [notes, setNotes] = useState("");
  const [createdOrderId, setCreatedOrderId] = useState<number | null>(null);
  const [customerProfile, setCustomerProfile] = useState<{ id: number; name: string; phone: string } | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setCheckoutStep("cart");
  }, [isOpen]);

  const summaryTotalCents = useMemo(
    () => cartItems.reduce((sum, item) => sum + Math.round(item.price * 100) * item.quantity, 0),
    [cartItems],
  );

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        store_id: tenant.store_id,
        items: cartItems.map((entry) => ({
          item_id: Number(entry.id),
          quantity: entry.quantity,
          selected_modifiers: (entry.selected_modifiers ?? []).map((mod) => ({ group_id: mod.group_id, option_id: mod.option_id })),
        })),
        customer_name: customerName,
        customer_phone: customerPhone,
        payment_method: paymentMethod,
        notes,
      };

      const endpointCandidates = [buildStorefrontApiUrl("/api/store/orders"), buildStorefrontApiUrl("/api/public/orders")];

      for (const endpoint of endpointCandidates) {
        const response = await fetch(endpoint, {
          credentials: "include",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        let data: any = null;
        try {
          data = await response.json();
        } catch {
          data = null;
        }

        if (response.ok) {
          return data;
        }

        if (response.status !== 404 && response.status !== 405) {
          throw new Error(data?.message || data?.detail || "Não foi possível enviar o pedido");
        }
      }

      throw new Error("Não foi possível enviar o pedido");
    },
  });

  const handleContinue = async () => {
    if (checkoutStep === "cart") return setCheckoutStep("identify");
    if (checkoutStep === "identify") {
      if (customerPhone.replace(/\D/g, "").length < 10) return;
      try {
        const params = new URLSearchParams({ phone: customerPhone.replace(/\D/g, "") });
        const response = await fetch(buildStorefrontApiUrl(`/api/store/customer-profile?${params.toString()}`), { credentials: "include" });
        if (response.ok) {
          const payload = await response.json();
          if (payload?.found && payload?.customer) {
            setCustomerProfile(payload.customer);
            setCustomerName(payload.customer.name || "");
            setCheckoutStep("returning");
            return;
          }
        }
      } catch {
        // fallback to new customer
      }
      setCheckoutStep("new-customer");
      return;
    }
    if (checkoutStep === "new-customer" || checkoutStep === "returning") return setCheckoutStep("payment");
    if (checkoutStep === "payment") {
      setCheckoutStep("submitting");
      try {
        const data = await checkoutMutation.mutateAsync();
        setCreatedOrderId(data?.daily_order_number ?? data?.order_number ?? data?.order_id ?? data?.id ?? null);
        setCheckoutStep("success");
      } catch {
        setCheckoutStep("payment");
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className={`fixed inset-0 z-50 ${theme === "dark" ? "bg-slate-950 text-white" : "bg-white text-slate-900"}`}>
      <style jsx global>{`
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
      <div className="h-full" style={{ animation: "slideUp 250ms ease-out" }}>
        <header className="fixed inset-x-0 top-0 z-10 border-b border-slate-200 bg-white p-4">
          <div className="mx-auto flex w-full max-w-xl items-center justify-between">
            <h2 className="text-base font-semibold italic">{checkoutStep === "cart" ? "Seu pedido" : checkoutStep === "identify" ? "Identificação" : checkoutStep === "new-customer" ? "Seus dados" : checkoutStep === "returning" ? "Bem-vindo de volta" : checkoutStep === "payment" ? "Pagamento" : "Pedido"}</h2>
            <Button variant="ghost" onClick={onClose}>Fechar</Button>
          </div>
        </header>

        <div className="h-screen overflow-y-auto px-4 pb-36 pt-20">
          <div className="mx-auto w-full max-w-xl space-y-4">
            {checkoutStep === "cart" && <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">{cartItems.map((entry) => <div key={`${entry.id}`} className="flex justify-between text-sm"><span>{entry.quantity}x {entry.name}</span><span>R$ {(entry.price * entry.quantity).toFixed(2)}</span></div>)}</div>}
            {checkoutStep === "identify" && <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4"><Input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="(11) 99999-9999" /></div>}
            {checkoutStep === "new-customer" && <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4"><Input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Seu nome" /></div>}
            {checkoutStep === "returning" && customerProfile && <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">Olá, {customerProfile.name}!</div>}
            {checkoutStep === "payment" && <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4"><Input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Seu nome" /><Input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="Telefone" /><div className="space-y-1">{["pix", "money", "card"].map((method) => <label key={method} className="flex items-center gap-2"><input type="radio" checked={paymentMethod === method} onChange={() => setPaymentMethod(method)} /><span>{method.toUpperCase()}</span></label>)}</div><textarea className="min-h-[80px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>}
            {checkoutStep === "success" && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-center"><p className="text-base font-semibold text-emerald-900">Pedido recebido</p>{createdOrderId && <p className="text-sm text-emerald-800">Número do pedido: #{createdOrderId}</p>}</div>}
          </div>
        </div>

        <footer className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white p-4">
          <div className="mx-auto flex w-full max-w-xl items-center justify-between gap-3">
            <p className="text-sm font-semibold">Total: R$ {(summaryTotalCents / 100).toFixed(2)}</p>
            {checkoutStep !== "success" ? (
              <Button className="flex-1" onClick={handleContinue} disabled={cartItems.length === 0 || checkoutStep === "submitting"}>{checkoutStep === "submitting" ? "Enviando..." : checkoutStep === "payment" ? "Confirmar pedido" : "Continuar"}</Button>
            ) : (
              <Button className="flex-1" onClick={() => { onOrderSuccess(); onClose(); }}>Voltar ao cardápio</Button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}
