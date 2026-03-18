"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TRACKING_STATUS_STEP, TRACKING_STEPS, normalizeTrackingStatus, resolveTrackingStep } from "@/lib/orderTrackingStatus";
import { buildStorefrontApiUrl } from "@/lib/storefrontApi";
import { formatCurrency, formatCurrencyFromCents } from "@/lib/currency";

const stepTitles: Record<string, string> = {
  cart: "Seu pedido",
  identify: "Identificação",
  "new-customer": "Seus dados",
  returning: "Bem-vindo de volta",
  address: "Endereço de entrega",
  payment: "Pagamento",
  submitting: "Enviando...",
  success: "",
};

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

interface CheckoutModalCartItem {
  id: string | number;
  menuItemId?: number;
  name: string;
  price: number;
  quantity: number;
  modifiers?: Array<{
    groupId: number;
    groupName: string;
    optionId: number;
    optionName: string;
    price: number;
    quantity: number;
  }> | string[];
  selected_modifiers?: Array<{ group_id: number; option_id: number; name: string; price_cents: number }>;
  note?: string;
  totalPrice?: number;
}

interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  cartItems: CheckoutModalCartItem[];
  onOrderSuccess: () => void;
  tenant: {
    slug: string;
    store_id: number;
    name: string;
    delivery_fee?: number;
  };
  theme?: "dark" | "white";
}

export function CheckoutModal({ isOpen, onClose, cartItems, onOrderSuccess, tenant, theme = "white" }: CheckoutModalProps) {
  const [localCartItems, setLocalCartItems] = useState(cartItems);
  const [checkoutStep, setCheckoutStep] = useState<CheckoutStep>("cart");
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [deliveryType, setDeliveryType] = useState<DeliveryType>("ENTREGA");
  const [paymentMethod, setPaymentMethod] = useState("pix");
  const [notes, setNotes] = useState("");
  const [createdOrderId, setCreatedOrderId] = useState<number | null>(null);
  const [orderSuccessData, setOrderSuccessData] = useState({
    orderNumber: 0,
    trackingToken: "",
    totalCents: 0,
    paymentMethod: "",
    deliveryType: "",
    pointsEarned: 0,
  });
  const [currentStatus, setCurrentStatus] = useState("pending");
  const [currentStatusStep, setCurrentStatusStep] = useState(1);
  const [customerProfile, setCustomerProfile] = useState<{ id: number; name: string; phone: string; addresses?: CustomerAddress[] } | null>(null);
  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [showNewAddressForm, setShowNewAddressForm] = useState(false);
  const [couponCode, setCouponCode] = useState("");
  const [redeemPoints, setRedeemPoints] = useState("0");

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


  const resolveModifiers = (item: CheckoutModalCartItem): Array<{ groupId: number; groupName: string; optionId: number; optionName: string; price: number; quantity: number }> => {
    if (item.modifiers && item.modifiers.length > 0 && typeof item.modifiers[0] !== "string") return item.modifiers as Array<{ groupId: number; groupName: string; optionId: number; optionName: string; price: number; quantity: number }>;
    if (item.modifiers && item.modifiers.length > 0 && typeof item.modifiers[0] === "string") {
      return item.modifiers.map((name, index) => ({
        groupId: 0,
        groupName: "",
        optionId: -(index + 1),
        optionName: String(name),
        price: 0,
        quantity: 1,
      }));
    }
    return (item.selected_modifiers ?? []).map((mod) => ({
      groupId: mod.group_id,
      groupName: "",
      optionId: mod.option_id,
      optionName: mod.name,
      price: mod.price_cents / 100,
      quantity: 1,
    }));
  };

  const resolveLineTotal = (item: CheckoutModalCartItem) => {
    if (typeof item.totalPrice === "number") return item.totalPrice;
    const extras = resolveModifiers(item).reduce((sum, mod) => sum + mod.price * mod.quantity, 0);
    return (item.price + extras) * item.quantity;
  };

  useEffect(() => {
    if (!isOpen) return;
    setLocalCartItems(cartItems);
    setCheckoutStep("cart");
    setCustomerName("");
    setCustomerEmail("");
    setCustomerPhone("");
    setDeliveryType("ENTREGA");
    setPaymentMethod("pix");
    setNotes("");
    setCustomerProfile(null);
    setCreatedOrderId(null);
    setOrderSuccessData({
      orderNumber: 0,
      trackingToken: "",
      totalCents: 0,
      paymentMethod: "",
      deliveryType: "",
      pointsEarned: 0,
    });
    setCurrentStatus("pending");
    setCurrentStatusStep(1);
    setShowNewAddressForm(false);
    setCouponCode("");
    setRedeemPoints("0");
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
    () => localCartItems.reduce((sum, item) => sum + Math.round(resolveLineTotal(item) * 100), 0),
    [localCartItems],
  );

  const cartTotal = useMemo(() => localCartItems.reduce((sum, item) => sum + resolveLineTotal(item), 0), [localCartItems]);
  const deliveryFee = deliveryType === "ENTREGA" ? Number(tenant.delivery_fee || 0) : 0;
  const checkoutTotal = cartTotal + deliveryFee;

  function saveCart(items: CheckoutModalProps["cartItems"]) {
    localStorage.setItem(`mobile-storefront-cart:${tenant.slug}`, JSON.stringify(items));
  }

  function persistCart(updatedCart: CheckoutModalProps["cartItems"]) {
    setLocalCartItems(updatedCart);
    saveCart(updatedCart);
    if (updatedCart.length === 0) {
      onClose();
    }
  }

  function handleIncrement(index: number) {
    const updatedCart = [...localCartItems];
    updatedCart[index] = {
      ...updatedCart[index],
      quantity: updatedCart[index].quantity + 1,
      totalPrice: resolveLineTotal(updatedCart[index]) / updatedCart[index].quantity * (updatedCart[index].quantity + 1),
    };
    persistCart(updatedCart);
  }

  function handleDecrement(index: number) {
    const updatedCart = [...localCartItems];
    if (updatedCart[index].quantity > 1) {
      updatedCart[index] = {
        ...updatedCart[index],
        quantity: updatedCart[index].quantity - 1,
        totalPrice: resolveLineTotal(updatedCart[index]) / updatedCart[index].quantity * (updatedCart[index].quantity - 1),
      };
      persistCart(updatedCart);
      return;
    }

    const filtered = updatedCart.filter((_, itemIndex) => itemIndex !== index);
    setLocalCartItems(filtered);
    saveCart(filtered);
    if (filtered.length === 0) {
      onClose();
    }
  }

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

  const customerIsNew = !customerProfile;

  function goBack() {
    switch (checkoutStep) {
      case "identify":
        return setCheckoutStep("cart");
      case "new-customer":
        return setCheckoutStep("identify");
      case "returning":
        return setCheckoutStep("identify");
      case "address":
        return setCheckoutStep(customerIsNew ? "new-customer" : "returning");
      case "payment":
        return setCheckoutStep(deliveryType === "ENTREGA" ? "address" : customerIsNew ? "new-customer" : "returning");
      default:
        return;
    }
  }

  useEffect(() => {
    if (checkoutStep !== "success") return;
    if (!orderSuccessData.trackingToken) return;

    let eventSource: EventSource | null = null;

    const syncTrackingStatus = async () => {
      try {
        const res = await fetch(buildStorefrontApiUrl(`/public/order/${orderSuccessData.trackingToken}`), {
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache",
            Pragma: "no-cache",
          },
        });
        if (res.ok) {
          const data = await res.json();
          const normalized = normalizeTrackingStatus(String(data.status || "pending"));
          setCurrentStatus(normalized);
          setCurrentStatusStep(resolveTrackingStep(normalized, data.status_step));
        }
      } catch {
        // silencioso
      }
    };

    const applyRealtimeUpdate = (message: {
      status?: string;
      status_raw?: string;
      status_step?: number;
      progress?: number;
      payload?: { status?: string; status_raw?: string; status_step?: number; progress?: number };
    }) => {
      const payload = message.payload && typeof message.payload === "object" ? message.payload : message;
      const rawStatus = String(payload.status_raw || payload.status || message.status_raw || message.status || "pending");
      const normalized = normalizeTrackingStatus(rawStatus);
      setCurrentStatus(normalized);
      setCurrentStatusStep(resolveTrackingStep(normalized, payload.status_step ?? message.status_step));
    };

    syncTrackingStatus();

    eventSource = new EventSource(buildStorefrontApiUrl(`/public/sse/${orderSuccessData.trackingToken}`));
    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as {
          status?: string;
          status_raw?: string;
          status_step?: number;
          progress?: number;
          payload?: { status?: string; status_raw?: string; status_step?: number; progress?: number };
        };
        applyRealtimeUpdate(parsed);
      } catch {
        // silencioso
      }
    };

    const interval = setInterval(syncTrackingStatus, 15000);

    return () => {
      clearInterval(interval);
      eventSource?.close();
    };
  }, [orderSuccessData.trackingToken, checkoutStep]);

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const selectedAddr = addressList.find((address) => address.id === selectedAddressId);
      const normalizedCep = addressForm.cep.replace(/\D/g, "");

      const deliveryAddress =
        deliveryType === "ENTREGA"
          ? selectedAddr && !showNewAddressForm
            ? {
                zip: selectedAddr.zip || selectedAddr.cep || "",
                cep: selectedAddr.cep || selectedAddr.zip || "",
                street: selectedAddr.street || "",
                number: selectedAddr.number || "",
                complement: selectedAddr.complement || "",
                neighborhood: selectedAddr.neighborhood || "",
                city: selectedAddr.city || "",
                state: selectedAddr.state || "",
              }
            : {
                zip: normalizedCep,
                cep: normalizedCep,
                street: addressForm.street || "",
                number: addressForm.number || "",
                complement: addressForm.complement || "",
                neighborhood: addressForm.neighborhood || "",
                city: addressForm.city || "",
                state: addressForm.state || "",
              }
          : undefined;

      const payload = {
        store_id: tenant.store_id,
        delivery_type: deliveryType,
        items: localCartItems.map((entry) => ({
          item_id: entry.menuItemId ?? Number(entry.id),
          name: entry.name,
          quantity: entry.quantity,
          unit_price: entry.price,
          total_price: entry.totalPrice,
          modifiers: resolveModifiers(entry).map((mod) => ({
            id: mod.optionId,
            name: mod.optionName,
            price: mod.price,
            quantity: mod.quantity,
          })),
          note: entry.note || "",
          selected_modifiers: resolveModifiers(entry).flatMap((mod) => Array.from({ length: mod.quantity }).map(() => ({ group_id: mod.groupId, option_id: mod.optionId }))),
        })),
        customer_name: customerName,
        customer_phone: customerPhone,
        customer_email: customerEmail || undefined,
        payment_method: paymentMethod,
        notes,
        delivery_address: deliveryAddress,
        street: deliveryAddress?.street,
        number: deliveryAddress?.number,
        complement: deliveryAddress?.complement,
        neighborhood: deliveryAddress?.neighborhood,
        city: deliveryAddress?.city,
        state: deliveryAddress?.state,
        cep: deliveryAddress?.cep,
        coupon_code: couponCode || undefined,
        redeem_points: Number(redeemPoints || 0),
      };

      const endpointCandidates = [buildStorefrontApiUrl("/api/store/orders"), buildStorefrontApiUrl("/api/public/orders")];

      let lastErrorMessage = "Não foi possível enviar o pedido";

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

        const responseMessage = data?.message || data?.detail || "Não foi possível enviar o pedido";
        lastErrorMessage = responseMessage;

        if (response.status >= 500 && endpoint !== endpointCandidates[endpointCandidates.length - 1]) {
          continue;
        }

        if (response.status !== 404 && response.status !== 405) {
          throw new Error(responseMessage);
        }
      }

      throw new Error(lastErrorMessage);
    },
  });

  const handleContinue = async () => {
    if (checkoutStep === "cart") {
      if (localCartItems.length === 0) {
        onClose();
        return;
      }
      return setCheckoutStep("identify");
    }

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
        const orderNumber = data?.daily_order_number ?? data?.order_number ?? data?.order_id ?? data?.id ?? 0;
        setCreatedOrderId(orderNumber);
        setOrderSuccessData({
          orderNumber,
          trackingToken: data?.tracking_token ?? "",
          totalCents: Number(data?.total_cents ?? data?.valor_total ?? data?.total ?? Math.round(checkoutTotal * 100)),
          paymentMethod: data?.payment_method ?? paymentMethod,
          deliveryType: data?.order_type ?? deliveryType,
          pointsEarned: Number(data?.points_earned ?? 0),
        });
        setCurrentStatus(normalizeTrackingStatus(String(data?.status ?? "pending")));
        setCurrentStatusStep(1);
        setCheckoutStep("success");
      } catch {
        setCheckoutStep("payment");
      }
    }
  };

  if (!isOpen) return null;

  const showBackButton = !(["cart", "submitting", "success"] as CheckoutStep[]).includes(checkoutStep);
  const showCloseButton = !(["submitting", "success"] as CheckoutStep[]).includes(checkoutStep);

  return (
    <div className={`fixed inset-0 z-50 ${theme === "dark" ? "bg-slate-950 text-white" : "bg-white text-slate-900"}`}>
      <style jsx global>{`
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
        @keyframes checkPop {
          0% { transform: scale(0); opacity: 0; }
          60% { transform: scale(1.2); opacity: 1; }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0.4); }
          50% { box-shadow: 0 0 0 6px rgba(34,197,94,0); }
        }
      `}</style>
      <div className="h-full" style={{ animation: "slideUp 250ms ease-out" }}>
        {checkoutStep !== "success" && (
          <header className="fixed inset-x-0 top-0 z-10 border-b border-slate-200 bg-white">
            <div className="mx-auto w-full max-w-xl space-y-3 px-5 py-4">
              <div className="flex items-center justify-between">
                {showBackButton ? (
                  <button type="button" onClick={goBack} className="flex items-center gap-1.5 text-sm text-slate-500">
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                      <path d="M11 4L6 9l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Voltar
                  </button>
                ) : (
                  <div style={{ width: 52 }} />
                )}
                <span className="text-center text-lg font-semibold italic" style={{ fontFamily: "var(--font-display)" }}>
                  {stepTitles[checkoutStep]}
                </span>
                {showCloseButton ? (
                  <button type="button" onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-full text-xl text-slate-500">
                    ×
                  </button>
                ) : (
                  <div style={{ width: 32 }} />
                )}
              </div>
              <div className="flex gap-2">
                {progressSteps.map((step, index) => {
                  const isDone = progressIndex >= index;
                  return <div key={step} className={`h-1 flex-1 rounded-full ${isDone ? "bg-emerald-500" : "bg-slate-200"}`} />;
                })}
              </div>
            </div>
          </header>
        )}

        <div className={`h-screen overflow-y-auto px-4 pb-36 ${checkoutStep === "success" ? "pt-6" : "pt-28"}`}>
          <div className="mx-auto w-full max-w-xl space-y-4">
            {checkoutStep === "cart" && (
              <>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  {localCartItems.map((item, index) => (
                    <div key={`${item.id}-${index}`} className="flex items-center justify-between border-b border-[var(--border-subtle)] py-3 last:border-0">
                      <div>
                        <div className="mb-1.5 text-[15px] font-semibold text-[var(--text-primary)]" style={{ fontFamily: "var(--font-display)" }}>
                          {item.name}
                        </div>
                        {resolveModifiers(item).length > 0 ? (
                          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4, lineHeight: 1.5 }}>
                            {resolveModifiers(item).map((modifier, modIndex) => (
                              <span key={`${modifier.optionId}-${modIndex}`}>
                                {modifier.quantity > 1 ? `${modifier.quantity}x ` : ""}
                                {modifier.optionName}
                                {modIndex < resolveModifiers(item).length - 1 ? " · " : ""}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {item.note ? (
                          <div style={{ fontSize: 11, color: "var(--text-secondary)", fontStyle: "italic", marginTop: 2 }}>Obs: {item.note}</div>
                        ) : null}
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => handleDecrement(index)}
                            className={`flex h-7 w-7 items-center justify-center rounded-full border bg-[var(--bg-card)] text-base font-normal text-[var(--text-primary)] transition-colors duration-150 hover:border-[var(--border-default)] hover:bg-[var(--bg-page)] ${
                              item.quantity === 1 ? "border-[rgba(239,68,68,0.4)] text-[#ef4444]" : "border-[var(--border-medium)]"
                            }`}
                          >
                            {item.quantity === 1 ? "×" : "−"}
                          </button>
                          <span className="min-w-6 text-center text-sm font-medium text-[var(--text-primary)]">{item.quantity}</span>
                          <button
                            type="button"
                            onClick={() => handleIncrement(index)}
                            className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--border-medium)] bg-[var(--bg-card)] text-base font-normal text-[var(--text-primary)] transition-colors duration-150 hover:border-[var(--border-default)] hover:bg-[var(--bg-page)]"
                          >
                            +
                          </button>
                        </div>
                      </div>
                      <span className="text-sm font-medium text-[var(--text-primary)]">{formatCurrency(resolveLineTotal(item))}</span>
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
                <Input value={couponCode} onChange={(e) => setCouponCode(e.target.value.toUpperCase())} placeholder="Cupom" />
                <Input type="number" min="0" value={redeemPoints} onChange={(e) => setRedeemPoints(e.target.value)} placeholder="Resgatar pontos" />
              </div>
            )}

            {checkoutStep === "success" && (
              <div className="space-y-4 rounded-2xl border border-emerald-100 bg-white p-5 shadow-sm">
                <div
                  style={{ animation: "checkPop 0.4s ease-out forwards" }}
                  className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100"
                >
                  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                    <path d="M8 16l6 6 10-12" stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <div className="text-center">
                  <p className="text-[24px] italic" style={{ fontFamily: "var(--font-display)" }}>
                    Pedido #{orderSuccessData.orderNumber || createdOrderId || ""} recebido!
                  </p>
                </div>
                <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                  <div className="flex justify-between"><span>Subtotal</span><span>{formatCurrency(cartTotal)}</span></div>
                  <div className="flex justify-between"><span>Delivery Fee</span><span>{formatCurrency(deliveryFee)}</span></div>
                  <div className="flex justify-between"><span>Total</span><span>{formatCurrencyFromCents(orderSuccessData.totalCents || Math.round(checkoutTotal * 100))}</span></div>
                  <div className="flex justify-between"><span>Pagamento</span><span>{String(orderSuccessData.paymentMethod || paymentMethod).toUpperCase()}</span></div>
                  <div className="flex justify-between"><span>Tipo</span><span>{orderSuccessData.deliveryType || deliveryType}</span></div>
                  {orderSuccessData.pointsEarned > 0 && <div className="text-emerald-700">+{orderSuccessData.pointsEarned} pontos ganhos</div>}
                </div>
                <div className="space-y-3 rounded-xl border border-slate-200 p-4">
                  <p className="text-sm font-semibold">Acompanhar pedido</p>
                  <div className="space-y-2">
                    {TRACKING_STEPS.map((step) => {
                      const done = TRACKING_STATUS_STEP[step.key] < (TRACKING_STATUS_STEP[currentStatus] || currentStatusStep || 1);
                      const isCurrent = step.key === currentStatus;
                      return (
                        <div key={step.key} className="flex items-center gap-2 text-sm">
                          <span
                            className={`inline-block h-3 w-3 rounded-full border ${done ? "border-emerald-500 bg-emerald-500" : "border-slate-300"}`}
                            style={isCurrent ? { animation: "pulse 1.2s infinite" } : undefined}
                          />
                          <span className={done ? "text-slate-900" : "text-slate-500"}>{step.label}</span>
                        </div>
                      );
                    })}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => window.open(`/pedido/${orderSuccessData.trackingToken}`, "_blank")}
                    disabled={!orderSuccessData.trackingToken}
                  >
                    Abrir página de tracking
                  </Button>
                </div>
                <Button
                  className="w-full"
                  onClick={() => {
                    onOrderSuccess();
                    onClose();
                  }}
                >
                  Voltar ao cardápio
                </Button>
              </div>
            )}
          </div>
        </div>

        {checkoutStep !== "success" && <footer className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white p-4">
          <div className="mx-auto flex w-full max-w-xl items-center justify-between gap-3">
            <div className="text-sm">
              <div className="flex justify-between gap-4"><span>Subtotal</span><span>{formatCurrency(cartTotal)}</span></div>
              <div className="flex justify-between gap-4"><span>Delivery Fee</span><span>{formatCurrency(deliveryFee)}</span></div>
              <div className="mt-1 flex justify-between gap-4 font-semibold"><span>Total</span><span>{formatCurrency(checkoutTotal)}</span></div>
            </div>
            <Button className="flex-1" onClick={handleContinue} disabled={localCartItems.length === 0 || checkoutStep === "submitting"}>
              {checkoutStep === "submitting" ? "Enviando..." : checkoutStep === "payment" ? "Confirmar pedido" : "Continuar"}
            </Button>
          </div>
        </footer>}
      </div>
    </div>
  );
}
