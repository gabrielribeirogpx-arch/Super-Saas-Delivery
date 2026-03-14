"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { buildStorefrontApiUrl } from "@/lib/storefrontApi";

type CheckoutStep =
  | "cart"
  | "identify"
  | "new-customer"
  | "returning"
  | "address"
  | "payment"
  | "submitting"
  | "success";

type DeliveryType = "ENTREGA" | "RETIRADA" | "MESA";

interface CustomerAddress {
  id: number;
  zip: string;
  cep?: string;
  street: string;
  number: string;
  complement?: string;
  neighborhood: string;
  city: string;
  state: string;
  is_default?: boolean;
}

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
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [deliveryType, setDeliveryType] = useState<DeliveryType>("ENTREGA");
  const [paymentMethod, setPaymentMethod] = useState("pix");
  const [notes, setNotes] = useState("");
  const [createdOrderId, setCreatedOrderId] = useState<number | null>(null);
  const [customerProfile, setCustomerProfile] = useState<{ id: number; name: string; phone: string; addresses?: CustomerAddress[] } | null>(null);
  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [showNewAddressForm, setShowNewAddressForm] = useState(false);

  const [addressForm, setAddressForm] = useState({
    zip: "",
    cep: "",
    street: "",
    number: "",
    complement: "",
    neighborhood: "",
    city: "",
    state: "",
  });
  const [cepLoading, setCepLoading] = useState(false);
  const [cepError, setCepError] = useState("");
  const [addressErrors, setAddressErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!isOpen) return;
    setCheckoutStep("cart");
    setCustomerName("");
    setCustomerEmail("");
    setCustomerPhone("");
    setDeliveryType("ENTREGA");
    setPaymentMethod("pix");
    setNotes("");
    setCustomerProfile(null);
    setCreatedOrderId(null);
    setShowNewAddressForm(false);
    setAddressErrors({});
    setCepError("");
    setAddressForm({
      zip: "",
      cep: "",
      street: "",
      number: "",
      complement: "",
      neighborhood: "",
      city: "",
      state: "",
    });
    setSelectedAddressId(null);
  }, [isOpen]);

  useEffect(() => {
    const defaultAddressId = customerProfile?.addresses?.find((address) => address.is_default)?.id ?? null;
    setSelectedAddressId(defaultAddressId);
  }, [customerProfile]);

  const summaryTotalCents = useMemo(
    () => cartItems.reduce((sum, item) => sum + Math.round(item.price * 100) * item.quantity, 0),
    [cartItems],
  );

  const progressSteps = deliveryType === "ENTREGA" ? ["cart", "identify", "address", "payment", "success"] : ["cart", "identify", "payment", "success"];
  const progressIndex = progressSteps.indexOf(checkoutStep);

  const addressList = customerProfile?.addresses ?? [];
  const hasSavedAddresses = addressList.length > 0;

  function formatCep(value: string) {
    const digits = value.replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 5) return digits;
    return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  }

  function handleAddressFieldChange(field: string, value: string) {
    setAddressForm((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "cep") {
        next.zip = value.replace(/\D/g, "");
      }
      return next;
    });
    setAddressErrors((prev) => ({ ...prev, [field]: "" }));
  }

  async function fetchCep(cep: string) {
    const cepLimpo = cep.replace(/\D/g, "");
    if (cepLimpo.length !== 8) return;
    setCepLoading(true);
    setCepError("");
    try {
      const res = await fetch(`https://viacep.com.br/ws/${cepLimpo}/json/`);
      const data = await res.json();
      if (data.erro) {
        setCepError("CEP não encontrado");
        return;
      }
      setAddressForm((prev) => ({
        ...prev,
        zip: cepLimpo,
        cep: formatCep(cepLimpo),
        street: data.logradouro || prev.street,
        neighborhood: data.bairro || prev.neighborhood,
        city: data.localidade || prev.city,
        state: data.uf || prev.state,
      }));
    } catch {
      setCepError("Erro ao buscar CEP");
    } finally {
      setCepLoading(false);
    }
  }

  function validateAddress() {
    if (deliveryType !== "ENTREGA") return true;

    if (hasSavedAddresses && !showNewAddressForm) {
      if (selectedAddressId) return true;
      setAddressErrors({ selectedAddressId: "Selecione um endereço" });
      return false;
    }

    const nextErrors: Record<string, string> = {};
    if (addressForm.cep.replace(/\D/g, "").length !== 8) nextErrors.cep = "Campo obrigatório";
    if (!addressForm.street.trim()) nextErrors.street = "Campo obrigatório";
    if (!addressForm.number.trim()) nextErrors.number = "Campo obrigatório";
    if (!addressForm.neighborhood.trim()) nextErrors.neighborhood = "Campo obrigatório";
    if (!addressForm.city.trim()) nextErrors.city = "Campo obrigatório";
    if (!addressForm.state.trim()) nextErrors.state = "Campo obrigatório";

    setAddressErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function goToNextAfterCustomer() {
    if (deliveryType === "ENTREGA") {
      setCheckoutStep("address");
    } else {
      setCheckoutStep("payment");
    }
  }

  function goToNextAfterAddress() {
    if (!validateAddress()) return;

    if (showNewAddressForm) {
      const newAddress: CustomerAddress = {
        id: Date.now(),
        zip: addressForm.cep.replace(/\D/g, ""),
        cep: addressForm.cep.replace(/\D/g, ""),
        street: addressForm.street,
        number: addressForm.number,
        complement: addressForm.complement,
        neighborhood: addressForm.neighborhood,
        city: addressForm.city,
        state: addressForm.state,
      };

      if (customerProfile) {
        setCustomerProfile((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            addresses: [...(prev.addresses ?? []), newAddress],
          };
        });
        setSelectedAddressId(newAddress.id);
      }
    }

    setCheckoutStep("payment");
  }

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const selectedAddr = addressList.find((address) => address.id === selectedAddressId);
      const normalizedCep = addressForm.cep.replace(/\D/g, "");

      const deliveryAddress =
        deliveryType === "ENTREGA"
          ? selectedAddr && !showNewAddressForm
            ? {
                zip: selectedAddr.zip,
                cep: selectedAddr.cep || selectedAddr.zip,
                street: selectedAddr.street,
                number: selectedAddr.number,
                complement: selectedAddr.complement || "",
                neighborhood: selectedAddr.neighborhood,
                city: selectedAddr.city,
                state: selectedAddr.state,
              }
            : {
                zip: normalizedCep,
                cep: normalizedCep,
                street: addressForm.street,
                number: addressForm.number,
                complement: addressForm.complement || "",
                neighborhood: addressForm.neighborhood,
                city: addressForm.city,
                state: addressForm.state,
              }
          : undefined;

      const payload = {
        store_id: tenant.store_id,
        delivery_type: deliveryType,
        items: cartItems.map((entry) => ({
          item_id: Number(entry.id),
          quantity: entry.quantity,
          selected_modifiers: (entry.selected_modifiers ?? []).map((mod) => ({ group_id: mod.group_id, option_id: mod.option_id })),
        })),
        customer_name: customerName,
        customer_phone: customerPhone,
        customer_email: customerEmail || undefined,
        payment_method: paymentMethod,
        notes,
        delivery_address: deliveryAddress,
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

    if (checkoutStep === "new-customer" || checkoutStep === "returning") {
      goToNextAfterCustomer();
      return;
    }

    if (checkoutStep === "address") {
      goToNextAfterAddress();
      return;
    }

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
          <div className="mx-auto w-full max-w-xl space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold italic">
                {checkoutStep === "cart"
                  ? "Seu pedido"
                  : checkoutStep === "identify"
                    ? "Identificação"
                    : checkoutStep === "new-customer"
                      ? "Seus dados"
                      : checkoutStep === "returning"
                        ? "Bem-vindo de volta"
                        : checkoutStep === "address"
                          ? "Endereço de entrega"
                          : checkoutStep === "payment"
                            ? "Pagamento"
                            : "Pedido"}
              </h2>
              <Button variant="ghost" onClick={onClose}>
                Fechar
              </Button>
            </div>
            <div className="flex gap-2">
              {progressSteps.map((step, index) => {
                const isDone = progressIndex >= index;
                return <div key={step} className={`h-1 flex-1 rounded-full ${isDone ? "bg-emerald-500" : "bg-slate-200"}`} />;
              })}
            </div>
          </div>
        </header>

        <div className="h-screen overflow-y-auto px-4 pb-36 pt-24">
          <div className="mx-auto w-full max-w-xl space-y-4">
            {checkoutStep === "cart" && (
              <>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  {cartItems.map((entry) => (
                    <div key={`${entry.id}`} className="flex justify-between text-sm">
                      <span>
                        {entry.quantity}x {entry.name}
                      </span>
                      <span>R$ {(entry.price * entry.quantity).toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <p className="text-sm font-semibold">Tipo de pedido</p>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    {(["ENTREGA", "RETIRADA", "MESA"] as DeliveryType[]).map((type) => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => setDeliveryType(type)}
                        className={`rounded-md border px-3 py-2 text-sm font-medium ${deliveryType === type ? "border-emerald-600 bg-emerald-50 text-emerald-700" : "border-slate-200"}`}
                      >
                        {type}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            {checkoutStep === "identify" && (
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
                <Input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="(11) 99999-9999" />
              </div>
            )}

            {checkoutStep === "new-customer" && (
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
                <Input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Seu nome" />
                <Input value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder="Seu e-mail" type="email" />
              </div>
            )}

            {checkoutStep === "returning" && customerProfile && (
              <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                <p>Olá, {customerProfile.name}!</p>
                <p className="text-slate-500">Vamos finalizar seu pedido.</p>
              </div>
            )}

            {checkoutStep === "address" && (
              <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                {hasSavedAddresses && !showNewAddressForm && (
                  <>
                    {addressList.map((address) => {
                      const selected = selectedAddressId === address.id;
                      return (
                        <button
                          key={address.id}
                          type="button"
                          onClick={() => {
                            setSelectedAddressId(address.id);
                            setAddressErrors((prev) => ({ ...prev, selectedAddressId: "" }));
                          }}
                          className={`w-full rounded-lg border p-3 text-left ${selected ? "border-emerald-500 bg-emerald-50" : "border-slate-200"}`}
                        >
                          <div className="flex items-start gap-3">
                            <span className="text-lg">📍</span>
                            <div className="flex-1">
                              <p className="text-sm font-medium">
                                {address.street}, {address.number} — {address.neighborhood}
                              </p>
                              <p className="text-xs text-slate-600">
                                {address.city} - {address.state} {formatCep(address.cep || address.zip)}
                              </p>
                            </div>
                            {address.is_default && <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">Padrão</span>}
                          </div>
                        </button>
                      );
                    })}
                    {addressErrors.selectedAddressId && <p className="text-xs text-red-600">{addressErrors.selectedAddressId}</p>}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setShowNewAddressForm(true);
                        setSelectedAddressId(null);
                      }}
                    >
                      + Usar outro endereço
                    </Button>
                  </>
                )}

                {(!hasSavedAddresses || showNewAddressForm) && (
                  <div className="space-y-2">
                    <div>
                      <Input
                        value={addressForm.cep}
                        onChange={(e) => handleAddressFieldChange("cep", formatCep(e.target.value))}
                        onBlur={(e) => fetchCep(e.target.value)}
                        placeholder="CEP *"
                        className={addressErrors.cep || cepError ? "border-red-500" : ""}
                      />
                      {cepLoading && <p className="mt-1 text-xs text-slate-500">Buscando CEP...</p>}
                      {cepError && <p className="mt-1 text-xs text-red-600">{cepError}</p>}
                      {addressErrors.cep && <p className="mt-1 text-xs text-red-600">{addressErrors.cep}</p>}
                    </div>
                    <div>
                      <Input
                        value={addressForm.street}
                        onChange={(e) => handleAddressFieldChange("street", e.target.value)}
                        placeholder="Rua *"
                        className={addressErrors.street ? "border-red-500" : ""}
                      />
                      {addressErrors.street && <p className="mt-1 text-xs text-red-600">{addressErrors.street}</p>}
                    </div>
                    <div>
                      <Input
                        value={addressForm.number}
                        onChange={(e) => handleAddressFieldChange("number", e.target.value)}
                        placeholder="Número *"
                        className={addressErrors.number ? "border-red-500" : ""}
                      />
                      {addressErrors.number && <p className="mt-1 text-xs text-red-600">{addressErrors.number}</p>}
                    </div>
                    <Input value={addressForm.complement} onChange={(e) => handleAddressFieldChange("complement", e.target.value)} placeholder="Complemento" />
                    <div>
                      <Input
                        value={addressForm.neighborhood}
                        onChange={(e) => handleAddressFieldChange("neighborhood", e.target.value)}
                        placeholder="Bairro *"
                        className={addressErrors.neighborhood ? "border-red-500" : ""}
                      />
                      {addressErrors.neighborhood && <p className="mt-1 text-xs text-red-600">{addressErrors.neighborhood}</p>}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Input value={addressForm.city} placeholder="Cidade *" readOnly className={addressErrors.city ? "border-red-500" : ""} />
                        {addressErrors.city && <p className="mt-1 text-xs text-red-600">{addressErrors.city}</p>}
                      </div>
                      <div>
                        <Input value={addressForm.state} placeholder="Estado *" readOnly className={addressErrors.state ? "border-red-500" : ""} />
                        {addressErrors.state && <p className="mt-1 text-xs text-red-600">{addressErrors.state}</p>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {checkoutStep === "payment" && (
              <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                <Input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Seu nome" />
                <Input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="Telefone" />
                <div className="space-y-1">
                  {["pix", "money", "card"].map((method) => (
                    <label key={method} className="flex items-center gap-2">
                      <input type="radio" checked={paymentMethod === method} onChange={() => setPaymentMethod(method)} />
                      <span>{method.toUpperCase()}</span>
                    </label>
                  ))}
                </div>
                <textarea className="min-h-[80px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
            )}

            {checkoutStep === "success" && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-center">
                <p className="text-base font-semibold text-emerald-900">Pedido recebido</p>
                {createdOrderId && <p className="text-sm text-emerald-800">Número do pedido: #{createdOrderId}</p>}
              </div>
            )}
          </div>
        </div>

        <footer className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white p-4">
          <div className="mx-auto flex w-full max-w-xl items-center justify-between gap-3">
            <p className="text-sm font-semibold">Total: R$ {(summaryTotalCents / 100).toFixed(2)}</p>
            {checkoutStep !== "success" ? (
              <Button className="flex-1" onClick={handleContinue} disabled={cartItems.length === 0 || checkoutStep === "submitting"}>
                {checkoutStep === "submitting" ? "Enviando..." : checkoutStep === "payment" ? "Confirmar pedido" : "Continuar"}
              </Button>
            ) : (
              <Button
                className="flex-1"
                onClick={() => {
                  onOrderSuccess();
                  onClose();
                }}
              >
                Voltar ao cardápio
              </Button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}
