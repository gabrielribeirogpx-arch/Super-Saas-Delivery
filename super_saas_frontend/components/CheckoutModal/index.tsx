"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, CreditCard, MapPin, ShoppingBag, Store, UtensilsCrossed, Wallet, X, LoaderCircle, UserRound, TicketPercent } from "lucide-react";
import styles from "./CheckoutModal.module.css";

import { fetchCheckoutPolicy, canUseCheckoutMethod, type CheckoutPolicy } from "@/lib/checkoutPolicy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { OrderSummary } from "@/components/storefront/OrderSummary";
import { cacheTrackingOrder, setOpenOrderSummary } from "@/lib/orderTrackingCache";
import { clearStorefrontCart, decrementOrRemoveCartItem, writeStorefrontCart } from "@/lib/storefrontCart";
import { completeOrderAttempt, endPublicOrderSubmission, PUBLIC_ORDER_ERROR_MESSAGE, PublicOrderSubmissionError, PublicOrderReviewRequiredError, startNewOrderAttempt, submitPublicOrder, tryBeginPublicOrderSubmission } from "@/lib/publicCheckout";
import { formatCurrency } from "@/lib/currency";

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

interface CheckoutHistoryState {
  checkoutSession: string;
  checkoutStep: CheckoutStep;
  checkoutIndex: number;
}

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

interface CheckoutOrderResponse {
  daily_order_number?: number;
  order_number?: number;
  order_id?: number;
  id?: number;
  tracking_token?: string;
  total_cents?: number | string | null;
  valor_total?: number | string | null;
  total?: number | string | null;
  payment_method?: string | null;
  order_type?: string | null;
  points_earned?: number | null;
  status?: string | null;
}

interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  cartItems: CheckoutModalCartItem[];
  onCartChange?: (items: CheckoutModalCartItem[]) => void;
  onOrderSuccess: () => void;
  tenant: {
    slug: string;
    store_id: number;
    name: string;
    delivery_fee?: number;
  };
  theme?: "dark" | "white";
}

export function CheckoutModal({ isOpen, onClose, cartItems, onCartChange, onOrderSuccess, tenant, theme = "white" }: CheckoutModalProps) {
  const [localCartItems, setLocalCartItems] = useState(cartItems);
  const [checkoutStep, setCheckoutStep] = useState<CheckoutStep>("cart");
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [deliveryType, setDeliveryType] = useState<DeliveryType>("ENTREGA");
  const [paymentMethod, setPaymentMethod] = useState("pix");
  const [paymentPolicy, setPaymentPolicy] = useState<CheckoutPolicy | null>(null);
  const [policyLoading, setPolicyLoading] = useState(true);
  const [policyError, setPolicyError] = useState("");
  const [policyReload, setPolicyReload] = useState(0);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    const controller = new AbortController();
    setPolicyLoading(true); setPolicyError(""); setPaymentPolicy(null);
    void fetchCheckoutPolicy(tenant.slug, controller.signal).then(policy => {
      if (!active) return;
      setPaymentPolicy(policy);
      setPaymentMethod(current => canUseCheckoutMethod(policy, current) ? current : policy.methods.find(method => method.available)?.id || "");
    }).catch(() => {
      if (active) setPolicyError("Não foi possível carregar as formas de pagamento. Tente novamente.");
    }).finally(() => { if (active) setPolicyLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [isOpen, tenant.slug, policyReload]);

  const [notes, setNotes] = useState("");
  const [orderSuccessData, setOrderSuccessData] = useState({
    orderNumber: 0,
    trackingToken: "",
    totalCents: 0,
    subtotalCents: 0,
    deliveryFeeCents: 0,
    paymentMethod: "",
    deliveryType: "",
    pointsEarned: 0,
  });
  const [customerProfile, setCustomerProfile] = useState<{ id: number; name: string; phone: string; addresses?: CustomerAddress[] } | null>(null);
  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [showNewAddressForm, setShowNewAddressForm] = useState(false);
  const [couponCode, setCouponCode] = useState("");
  const [redeemPoints, setRedeemPoints] = useState("0");
  const [submissionError, setSubmissionError] = useState("");
  const [submissionNeedsReview, setSubmissionNeedsReview] = useState(false);
  const submissionInFlight = useRef(false);
  const checkoutSession = useRef<string | null>(null);
  const checkoutHistoryIndex = useRef(0);
  const checkoutCompleted = useRef(false);
  const onCloseRef = useRef(onClose);

  onCloseRef.current = onClose;

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
    setOrderSuccessData({
      orderNumber: 0,
      trackingToken: "",
      totalCents: 0,
    subtotalCents: 0,
    deliveryFeeCents: 0,
      paymentMethod: "",
      deliveryType: "",
      pointsEarned: 0,
    });
    setShowNewAddressForm(false);
    setCouponCode("");
    setRedeemPoints("0");
    setSubmissionError("");
    submissionInFlight.current = false;
    checkoutCompleted.current = false;
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
    if (!isOpen) {
      checkoutSession.current = null;
      checkoutHistoryIndex.current = 0;
      return;
    }

    if (!checkoutSession.current) {
      checkoutSession.current = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      checkoutHistoryIndex.current = 1;
      window.history.pushState(
        {
          ...(typeof window.history.state === "object" && window.history.state !== null ? window.history.state : {}),
          checkoutSession: checkoutSession.current,
          checkoutStep: "cart",
          checkoutIndex: 1,
        } satisfies CheckoutHistoryState,
        "",
        window.location.href,
      );
    }

    const handlePopState = (event: PopStateEvent) => {
      const state = event.state as Partial<CheckoutHistoryState> | null;
      const belongsToCheckout = state?.checkoutSession === checkoutSession.current;

      if (checkoutCompleted.current) {
        onCloseRef.current();
        if (belongsToCheckout && typeof state?.checkoutIndex === "number" && state.checkoutIndex > 0) {
          window.history.go(-state.checkoutIndex);
        }
        return;
      }

      if (belongsToCheckout && state?.checkoutStep) {
        checkoutHistoryIndex.current = state.checkoutIndex ?? 0;
        setCheckoutStep(state.checkoutStep);
        return;
      }

      checkoutHistoryIndex.current = 0;
      onCloseRef.current();
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [isOpen]);

  function navigateToCheckoutStep(step: CheckoutStep, mode: "push" | "replace" = "push") {
    const session = checkoutSession.current;
    if (!session) {
      setCheckoutStep(step);
      return;
    }

    const currentHistoryState = window.history.state;
    if (
      mode === "push" &&
      currentHistoryState?.checkoutSession === session &&
      currentHistoryState?.checkoutStep === step
    ) {
      setCheckoutStep(step);
      return;
    }

    const nextIndex = mode === "push" ? checkoutHistoryIndex.current + 1 : checkoutHistoryIndex.current;
    const nextState: CheckoutHistoryState = {
      ...(typeof currentHistoryState === "object" && currentHistoryState !== null ? currentHistoryState : {}),
      checkoutSession: session,
      checkoutStep: step,
      checkoutIndex: nextIndex,
    };
    const historyMethod = mode === "push" ? window.history.pushState : window.history.replaceState;
    historyMethod.call(window.history, nextState, "", window.location.href);
    checkoutHistoryIndex.current = nextIndex;
    setCheckoutStep(step);
  }

  function closeCheckout() {
    const entriesToMenu = checkoutHistoryIndex.current;
    onCloseRef.current();
    if (entriesToMenu > 0) window.history.go(-entriesToMenu);
  }

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
    writeStorefrontCart(localStorage, tenant.slug, items);
    window.dispatchEvent(new CustomEvent("storefront-cart-change"));
  }

  function persistCart(updatedCart: CheckoutModalProps["cartItems"]) {
    setLocalCartItems(updatedCart);
    onCartChange?.(updatedCart);
    saveCart(updatedCart);
    if (updatedCart.length === 0) {
      closeCheckout();
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
    const normalized = localCartItems.map((item) => ({ ...item, totalPrice: resolveLineTotal(item) }));
    persistCart(decrementOrRemoveCartItem(normalized, index));
  }

  const progressSteps = deliveryType === "ENTREGA" ? ["cart", "identify", "address", "payment"] : ["cart", "identify", "payment"];
  const visualStep = checkoutStep === "new-customer" || checkoutStep === "returning" ? "identify" : checkoutStep === "submitting" ? "payment" : checkoutStep;
  const progressIndex = progressSteps.indexOf(visualStep);
  const contentRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.focus({ preventScroll: true });
    const containFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), a[href], summary, [tabindex="0"]') ?? []).filter(element => element.getClientRects().length > 0);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialogRef.current)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", containFocus);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", containFocus);
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    contentRef.current?.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
    dialogRef.current?.focus({ preventScroll: true });
  }, [checkoutStep, isOpen]);

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
      navigateToCheckoutStep("address");
    } else {
      navigateToCheckoutStep("payment");
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

    navigateToCheckoutStep("payment");
  }

  function goBack() {
    window.history.back();
  }

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

      return submitPublicOrder<CheckoutOrderResponse>(payload, tenant.slug);
    },
  });

  const handleContinue = async () => {
    if (checkoutStep === "cart") {
      if (localCartItems.length === 0) {
        closeCheckout();
        return;
      }
      return navigateToCheckoutStep("identify");
    }

    if (checkoutStep === "identify") {
      const normalizedPhone = customerPhone.replace(/\D/g, "");
      if (normalizedPhone.length < 10) return;

      if (customerProfile?.phone?.replace(/\D/g, "") === normalizedPhone) {
        setCustomerName(customerProfile.name || "");
        navigateToCheckoutStep("returning");
        return;
      }

      navigateToCheckoutStep("new-customer");
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
      if (policyLoading || !canUseCheckoutMethod(paymentPolicy, paymentMethod)) return;
      if (!tryBeginPublicOrderSubmission(submissionInFlight)) return;
      setSubmissionError("");
      setSubmissionNeedsReview(false);
      navigateToCheckoutStep("submitting", "replace");
      try {
        const data = await checkoutMutation.mutateAsync();
        const orderNumber = data?.daily_order_number ?? data?.order_number ?? data?.order_id ?? data?.id ?? 0;
        setOrderSuccessData({
          orderNumber,
          trackingToken: data?.tracking_token ?? "",
          subtotalCents: Math.round(cartTotal * 100),
          deliveryFeeCents: Math.round(deliveryFee * 100),
          totalCents: Number(data?.total_cents ?? data?.valor_total ?? data?.total ?? Math.round(checkoutTotal * 100)),
          paymentMethod: data?.payment_method ?? paymentMethod,
          deliveryType: data?.order_type ?? deliveryType,
          pointsEarned: Number(data?.points_earned ?? 0),
        });
        cacheTrackingOrder({
          token: data?.tracking_token ?? "",
          tenant: tenant.slug,
          orderNumber,
          subtotalCents: Math.round(cartTotal * 100),
          deliveryFeeCents: Math.round(deliveryFee * 100),
          totalCents: Number(data?.total_cents ?? data?.valor_total ?? data?.total ?? Math.round(checkoutTotal * 100)),
          paymentMethod: data?.payment_method ?? paymentMethod,
          deliveryType: data?.order_type ?? deliveryType,
          pointsEarned: Number(data?.points_earned ?? 0),
          status: data?.status ?? "pending",
        });
        setOpenOrderSummary(tenant.slug, data?.tracking_token || null);
        clearStorefrontCart(localStorage, tenant.slug);
        completeOrderAttempt(data);
        checkoutCompleted.current = true;
        navigateToCheckoutStep("success", "replace");
      } catch (error) {
        setSubmissionError(error instanceof PublicOrderSubmissionError ? error.message : PUBLIC_ORDER_ERROR_MESSAGE);
        setSubmissionNeedsReview(error instanceof PublicOrderReviewRequiredError);
        setPolicyReload(value => value + 1);
        navigateToCheckoutStep("payment", "replace");
      } finally {
        endPublicOrderSubmission(submissionInFlight);
      }
    }
  };

  if (!isOpen) return null;

  const showBackButton = !(["cart", "submitting", "success"] as CheckoutStep[]).includes(checkoutStep);
  const showCloseButton = !(["submitting", "success"] as CheckoutStep[]).includes(checkoutStep);

  return (
    <div className={styles.overlay} data-theme={theme}>
      <div ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="checkout-title" className={styles.dialog}>
        {checkoutStep !== "success" && (
          <header className={styles.header}>
            <div className={styles.topline}>
              {showBackButton ? <button type="button" onClick={goBack} className={styles.iconButton} aria-label="Voltar"><ArrowLeft size={20} aria-hidden="true" /></button> : <span className={styles.storeIcon}><ShoppingBag size={20} aria-hidden="true" /></span>}
              <div className={styles.heading}><p className={styles.storeName}>{tenant.name}</p><h2 id="checkout-title">{stepTitles[checkoutStep]}</h2></div>
              {showCloseButton ? <button type="button" onClick={closeCheckout} className={styles.iconButton} aria-label="Fechar checkout"><X size={20} aria-hidden="true" /></button> : <span className={styles.iconSpacer} />}
            </div>
            <ol className={styles.progress} aria-label="Etapas do pedido">
              {progressSteps.map((step, index) => <li key={step} aria-current={index === progressIndex ? "step" : undefined} data-complete={index < progressIndex}>
                <span className={styles.progressNumber}>{index < progressIndex ? <Check size={12} aria-hidden="true" /> : index + 1}</span><span>{step === "cart" ? "Pedido" : step === "identify" ? "Dados" : step === "address" ? "Entrega" : "Pagamento"}</span>
              </li>)}
            </ol>
          </header>
        )}
        {checkoutStep === "success" && <h2 id="checkout-title" className="sr-only">Pedido recebido</h2>}
        <div ref={contentRef} className={styles.content} aria-busy={checkoutStep === "submitting"}>
          <div className={styles.contentInner}>
            {checkoutStep === "cart" && (
              <>
                <div className={styles.card}>
                  {localCartItems.map((item, index) => (
                    <div key={`${item.id}-${index}`} className={styles.cartItem}>
                      <div className={styles.itemDetails}>
                        <div className="mb-1.5 text-[15px] font-semibold text-[var(--text-primary)]" style={{ fontFamily: "var(--font-display)" }}>
                          {item.name}
                        </div>
                        {resolveModifiers(item).length > 0 ? (
                          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4, lineHeight: 1.5 }}>
                            {resolveModifiers(item).map((modifier, modIndex) => (
                              <span key={`${modifier.optionId}-${modIndex}`}>
                                + {modifier.quantity > 1 ? `${modifier.quantity}x ` : ""}
                                {modifier.optionName}
                                {modIndex < resolveModifiers(item).length - 1 ? " · " : ""}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {item.note ? (
                          <div style={{ fontSize: 11, color: "var(--text-secondary)", fontStyle: "italic", marginTop: 2 }}>Obs.: {item.note}</div>
                        ) : null}
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => handleDecrement(index)}
                            aria-label={item.quantity === 1 ? `Remover ${item.name}` : `Diminuir quantidade de ${item.name}`}
                            className={`flex h-10 w-10 items-center justify-center rounded-full border bg-[var(--bg-card)] text-lg font-normal text-[var(--text-primary)] transition-colors duration-150 hover:border-[var(--border-default)] hover:bg-[var(--bg-page)] ${
                              item.quantity === 1 ? "border-[rgba(239,68,68,0.4)] text-[#ef4444]" : "border-[var(--border-medium)]"
                            }`}
                          >
                            {item.quantity === 1 ? "×" : "−"}
                          </button>
                          <span className="min-w-6 text-center text-sm font-medium text-[var(--text-primary)]">{item.quantity}</span>
                          <button
                            type="button"
                            onClick={() => handleIncrement(index)}
                            aria-label={`Aumentar quantidade de ${item.name}`}
                            className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border-medium)] bg-[var(--bg-card)] text-lg font-normal text-[var(--text-primary)] transition-colors duration-150 hover:border-[var(--border-default)] hover:bg-[var(--bg-page)]"
                          >
                            +
                          </button>
                        </div>
                      </div>
                      <span className={styles.linePrice}>{formatCurrency(resolveLineTotal(item))}</span>
                    </div>
                  ))}
                </div>
                <div className={styles.card}>
                  <div className={styles.sectionHeading}><ShoppingBag size={18} aria-hidden="true" /><h3>Tipo de pedido</h3></div><p className={styles.helper}>Como você prefere receber?</p>
                  <div className={styles.deliveryOptions}>
                    {(["ENTREGA", "RETIRADA", "MESA"] as DeliveryType[]).map((type) => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => setDeliveryType(type)}
                        aria-pressed={deliveryType === type}
                        className={styles.deliveryOption}
                      >
                        {type === "ENTREGA" ? <MapPin size={21} aria-hidden="true" /> : type === "RETIRADA" ? <Store size={21} aria-hidden="true" /> : <UtensilsCrossed size={21} aria-hidden="true" />}<span>{type}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            {checkoutStep === "identify" && (
              <div className={styles.card}>
                <div className={styles.introIcon}><UserRound size={24} aria-hidden="true" /></div><h3>Vamos começar pelo seu telefone</h3><p className={styles.helper}>Usaremos esse número para identificar seu pedido.</p><label className={styles.field}>Celular<Input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="(11) 99999-9999" type="tel" autoComplete="tel" inputMode="tel" /></label>
              </div>
            )}

            {checkoutStep === "new-customer" && (
              <div className={styles.card}>
                <label className={styles.field}>Nome<Input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Seu nome" autoComplete="name" /></label>
                <label className={styles.field}>E-mail <span className={styles.optional}>(opcional)</span><Input value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder="Seu e-mail" type="email" autoComplete="email" /></label>
              </div>
            )}

            {checkoutStep === "returning" && customerProfile && (
              <div className={styles.welcomeCard}>
                <div className={styles.introIcon}><Check size={24} aria-hidden="true" /></div><h3>Olá, {customerProfile.name}!</h3>
                <p className="text-slate-500">Vamos finalizar seu pedido.</p>
              </div>
            )}

            {checkoutStep === "address" && (
              <div className={styles.card}>
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
                          className={styles.addressOption} aria-pressed={selected}
                        >
                          <div className="flex items-start gap-3">
                            <MapPin size={20} aria-hidden="true" />
                            <div className="flex-1">
                              <p className="text-sm font-medium">
                                {address.street}, {address.number} — {address.neighborhood}
                              </p>
                              <p className="text-xs text-slate-600">
                                {address.city} - {address.state} {formatCep(address.cep || address.zip)}
                              </p>
                            </div>
                            {address.is_default && <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">Padrão</span>}
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
                  <div className={styles.addressFields}>
                    <div>
                      <label className={styles.field}>CEP<Input autoComplete="postal-code" inputMode="numeric"
                        value={addressForm.cep}
                        onChange={(e) => handleAddressFieldChange("cep", formatCep(e.target.value))}
                        onBlur={(e) => fetchCep(e.target.value)}
                        placeholder="CEP *"
                        className={addressErrors.cep || cepError ? "border-red-500" : ""}
                      /></label>
                      {cepLoading && <p className="mt-1 text-xs text-slate-500">Buscando CEP...</p>}
                      {cepError && <p className="mt-1 text-xs text-red-600">{cepError}</p>}
                      {addressErrors.cep && <p className="mt-1 text-xs text-red-600">{addressErrors.cep}</p>}
                    </div>
                    <div>
                      <label className={styles.field}>Rua<Input autoComplete="address-line1"
                        value={addressForm.street}
                        onChange={(e) => handleAddressFieldChange("street", e.target.value)}
                        placeholder="Rua *"
                        className={addressErrors.street ? "border-red-500" : ""}
                      /></label>
                      {addressErrors.street && <p className="mt-1 text-xs text-red-600">{addressErrors.street}</p>}
                    </div>
                    <div>
                      <label className={styles.field}>Número<Input autoComplete="off"
                        value={addressForm.number}
                        onChange={(e) => handleAddressFieldChange("number", e.target.value)}
                        placeholder="Número *"
                        className={addressErrors.number ? "border-red-500" : ""}
                      /></label>
                      {addressErrors.number && <p className="mt-1 text-xs text-red-600">{addressErrors.number}</p>}
                    </div>
                    <label className={styles.field}>Complemento (opcional)<Input autoComplete="address-line2" value={addressForm.complement} onChange={(e) => handleAddressFieldChange("complement", e.target.value)} placeholder="Complemento" /></label>
                    <div>
                      <label className={styles.field}>Bairro<Input autoComplete="off"
                        value={addressForm.neighborhood}
                        onChange={(e) => handleAddressFieldChange("neighborhood", e.target.value)}
                        placeholder="Bairro *"
                        className={addressErrors.neighborhood ? "border-red-500" : ""}
                      /></label>
                      {addressErrors.neighborhood && <p className="mt-1 text-xs text-red-600">{addressErrors.neighborhood}</p>}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className={styles.field}>Cidade<Input autoComplete="address-level2" value={addressForm.city} placeholder="Cidade *" readOnly className={addressErrors.city ? "border-red-500" : ""} /></label>
                        {addressErrors.city && <p className="mt-1 text-xs text-red-600">{addressErrors.city}</p>}
                      </div>
                      <div>
                        <label className={styles.field}>Estado<Input autoComplete="address-level1" value={addressForm.state} placeholder="Estado *" readOnly className={addressErrors.state ? "border-red-500" : ""} /></label>
                        {addressErrors.state && <p className="mt-1 text-xs text-red-600">{addressErrors.state}</p>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {checkoutStep === "payment" && (
              <div className={styles.card}>
                {submissionError && (
                  <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {submissionError}
                    {submissionNeedsReview && <div className="mt-2 space-y-2">
                      <p>Use a opção abaixo apenas se confirmou com a loja que o pedido anterior não existe.</p>
                      <button type="button" className="underline font-semibold" onClick={() => {
                        startNewOrderAttempt(tenant.slug); setSubmissionError(""); setSubmissionNeedsReview(false);
                      }}>Já conferi: iniciar outro pedido</button>
                    </div>}
                  </div>
                )}
                <label className={styles.field}>Nome<Input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Seu nome" autoComplete="name" /></label>
                <label className={styles.field}>Celular<Input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="Telefone" type="tel" autoComplete="tel" /></label>
                <div className={styles.paymentMethods}><div className={styles.sectionHeading}><Wallet size={18} aria-hidden="true" /><h3>Como prefere pagar?</h3></div>
                  {policyLoading && <p role="status">Carregando formas de pagamento...</p>}
                  {policyError && <div role="alert"><p>{policyError}</p><Button type="button" variant="outline" onClick={() => setPolicyReload(value => value + 1)}>Tentar novamente</Button></div>}
                  {!policyLoading && paymentPolicy?.message && <p role="status" className="text-sm text-slate-700">{paymentPolicy.message}</p>}
                  {!policyLoading && paymentPolicy?.methods.map(method => (
                    <label key={method.id} className={styles.paymentOption} data-selected={paymentMethod === method.id && method.available} data-disabled={!method.available}>
                      <input name="payment-method" type="radio" value={method.id} disabled={!method.available} checked={paymentMethod === method.id} onChange={() => setPaymentMethod(method.id)} />
                      <span className={styles.paymentIcon}>{method.id.includes("card") ? <CreditCard size={20} aria-hidden="true" /> : <Wallet size={20} aria-hidden="true" />}</span><span>{method.label}{!method.available ? " — indisponível" : ""}</span>
                    </label>
                  ))}
                </div>
                <label className={styles.field}>Observações <span className={styles.optional}>(opcional)</span><textarea placeholder="Algo que a loja precisa saber?" value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
                <details className={styles.benefits}><summary><TicketPercent size={18} aria-hidden="true" /> Cupom e pontos <span className={styles.optional}>Opcional</span></summary><label className={styles.field}>Cupom<Input value={couponCode} onChange={(e) => setCouponCode(e.target.value.toUpperCase())} placeholder="Cupom" /></label><label className={styles.field}>Resgatar pontos<Input type="number" min="0" value={redeemPoints} onChange={(e) => setRedeemPoints(e.target.value)} placeholder="Resgatar pontos" /></label></details>
              </div>
            )}

            {checkoutStep === "submitting" && <div className={styles.submitting} role="status"><LoaderCircle size={36} aria-hidden="true" /><h3>Enviando seu pedido</h3><p>Aguarde a confirmação da loja por aqui.</p></div>}
            {checkoutStep === "success" && (
              <OrderSummary
                order={{ ...orderSuccessData, token: orderSuccessData.trackingToken, tenant: tenant.slug, createdAt: 0 }}
                onBack={() => {
              setOpenOrderSummary(tenant.slug, null);
                  onOrderSuccess();
                  closeCheckout();
                }}
              />
            )}
          </div>
        </div>

        {checkoutStep !== "success" && <footer className={styles.footer}>
          <div className={styles.totals}>
            <div><span>Subtotal</span><span>{formatCurrency(cartTotal)}</span></div>
            <div><span>Taxa de entrega</span><span>{formatCurrency(deliveryFee)}</span></div>
            <div className={styles.grandTotal}><span>Total do pedido</span><strong>{formatCurrency(checkoutTotal)}</strong></div>
          </div>
          <Button className={styles.continueButton} onClick={handleContinue} disabled={localCartItems.length === 0 || checkoutStep === "submitting" || (checkoutStep === "payment" && (policyLoading || !canUseCheckoutMethod(paymentPolicy, paymentMethod)))}>
            {checkoutStep === "submitting" ? <LoaderCircle className={styles.spinner} size={18} aria-hidden="true" /> : null}
            {checkoutStep === "submitting" ? "Enviando..." : checkoutStep === "payment" ? "Confirmar pedido" : "Continuar"}
            {checkoutStep !== "submitting" && <ArrowRight size={18} aria-hidden="true" />}
          </Button>
        </footer>}
      </div>
    </div>
  );
}
