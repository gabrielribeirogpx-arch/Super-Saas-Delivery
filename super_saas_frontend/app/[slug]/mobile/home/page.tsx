"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { storefrontFetch } from "@/lib/storefrontApi";
import { submitPublicOrder } from "@/lib/publicCheckout";
import { CheckoutModal } from "@/components/CheckoutModal";

type CheckoutStep = "cart" | "identify" | "new-customer" | "returning" | "payment" | "submitting" | "success";

interface CheckoutErrors {
  customerPhone?: string;
  zip?: string;
  street?: string;
  number?: string;
  district?: string;
  city?: string;
  state?: string;
  changeFor?: string;
  tableNumber?: string;
}

interface PublicMenuItem {
  id: number;
  category_id: number | null;
  name: string;
  description?: string | null;
  price_cents: number;
  image_url?: string | null;
  modifier_groups?: ModifierGroup[];
}

interface ModifierOption {
  id: number;
  name: string;
  description?: string | null;
  price_delta: number | string;
  is_default: boolean;
  is_active: boolean;
  order_index: number;
}

interface ModifierGroup {
  id: number;
  name: string;
  description?: string | null;
  required: boolean;
  min_required?: number;
  min_selection: number;
  max_selection: number;
  order_index: number;
  options: ModifierOption[];
}

interface PublicMenuCategory {
  id: number;
  name: string;
  sort_order: number;
  items: PublicMenuItem[];
}

interface PublicMenuResponse {
  tenant_id: number;
  slug: string;
  tenant?: {
    delivery_fee?: number;
  };
  categories: PublicMenuCategory[];
  items_without_category: PublicMenuItem[];
}

interface CartItem {
  item: PublicMenuItem;
  quantity: number;
  selected_modifiers: Array<{ group_id: number; option_id: number; name: string; price_cents: number }>;
}

interface DeliveryAddress {
  zip: string;
  street: string;
  number: string;
  complement: string;
  district: string;
  city: string;
  state: string;
  reference: string;
}

interface StorefrontCustomerProfileResponse {
  found: boolean;
  customer: {
    id: number;
    name: string;
    phone: string;
    email: string | null;
    addresses: Array<{ id: number; zip: string; street: string; number: string; complement: string | null; neighborhood: string; city: string; state: string; is_default: boolean }>;
    points: { available: number; lifetime: number } | null;
    active_benefits: Array<{ id: number; type: string; value: number; coupon_code: string | null }>;
    tags: string[];
    stats: { total_orders: number; total_spent: number } | null;
  } | null;
}

interface CreateOrderResponse {
  order_id?: number;
  id?: number;
  order_number?: number;
  daily_order_number?: number;
  points_earned?: number;
  estimated_time?: string | number | null;
  total?: string | number | null;
}

interface OrderSuccessData {
  order_id: number | null;
  points_earned: number;
  estimated_time: string;
  total: number;
  items: CartItem[];
}

export default function MobileHomePage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [cart, setCart] = useState<CartItem[]>([]);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [address, setAddress] = useState<DeliveryAddress>({ zip: "", street: "", number: "", complement: "", district: "", city: "", state: "", reference: "" });
  const [notes, setNotes] = useState("");
  const [deliveryType, setDeliveryType] = useState("ENTREGA");
  const [tableNumber, setTableNumber] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("pix");
  const [changeFor, setChangeFor] = useState("");
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [checkoutMessage, setCheckoutMessage] = useState<string | null>(null);
  const [couponCode, setCouponCode] = useState("");
  const [couponFeedback, setCouponFeedback] = useState<{ type: "error" | "success"; text: string } | null>(null);
  const [appliedCouponId, setAppliedCouponId] = useState<number | null>(null);
  const [isCouponApplied, setIsCouponApplied] = useState(false);
  const [discountAmountCents, setDiscountAmountCents] = useState(0);
  const [newTotalCents, setNewTotalCents] = useState(0);
  const [sheetItem, setSheetItem] = useState<PublicMenuItem | null>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<number, number[]>>({});
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState<CheckoutStep>("cart");
  const [customerProfile, setCustomerProfile] = useState<StorefrontCustomerProfileResponse["customer"]>(null);
  const [isIdentifyingCustomer, setIsIdentifyingCustomer] = useState(false);
  const [identifyError, setIdentifyError] = useState<string | null>(null);
  const [checkoutErrors, setCheckoutErrors] = useState<CheckoutErrors>({});
  const [createdOrderId, setCreatedOrderId] = useState<number | null>(null);
  const [isCartStorageReady, setIsCartStorageReady] = useState(false);
  const [orderSuccessData, setOrderSuccessData] = useState<OrderSuccessData | null>(null);

  const cartStorageKey = useMemo(() => `mobile-storefront-cart:${slug}`, [slug]);

  useEffect(() => {
    const raw = window.localStorage.getItem(`storefront-customer:${slug}`);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as StorefrontCustomerProfileResponse["customer"];
      if (!parsed?.phone) return;
      setCustomerProfile(parsed);
      setCustomerPhone(formatPhone(parsed.phone));
      setCustomerName(parsed.name || "");
      setCustomerId(parsed.id || null);
    } catch {
      window.localStorage.removeItem(`storefront-customer:${slug}`);
    }
  }, [slug]);

  const menuQuery = useQuery({
    queryKey: ["public-menu", slug],
    queryFn: async () => {
      const response = await storefrontFetch(`/api/public/${slug}/menu`, {
        credentials: "include",
      }, slug);
      if (!response.ok) {
        throw new Error("Falha ao carregar cardápio");
      }
      return (await response.json()) as PublicMenuResponse;
    },
  });

  useEffect(() => {
    const cleanPhone = customerPhone.replace(/\D/g, "");
    if (cleanPhone.length < 10) {
      return;
    }

    if (customerProfile?.phone?.replace(/\D/g, "") !== cleanPhone) {
      return;
    }

    setCustomerId(customerProfile.id ?? null);
    setCustomerName((prev) => prev || customerProfile.name || "");

    const defaultAddress = customerProfile.addresses?.find((entry) => entry.is_default) ?? customerProfile.addresses?.[0];
    if (!defaultAddress) {
      return;
    }

    setAddress((prev) => ({
      zip: prev.zip || defaultAddress.zip || defaultAddress.cep || "",
      street: prev.street || defaultAddress.street || "",
      number: prev.number || defaultAddress.number || "",
      complement: prev.complement || defaultAddress.complement || "",
      district: prev.district || defaultAddress.neighborhood || "",
      city: prev.city || defaultAddress.city || "",
      state: prev.state || defaultAddress.state || "",
      reference: prev.reference || "",
    }));
  }, [customerPhone, customerProfile]);

  const normalizeDigits = (value: string) => value.replace(/\D/g, "");

  const formatPhone = (value: string) => {
    const digits = normalizeDigits(value).slice(0, 11);
    if (digits.length <= 2) return digits;
    if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
    if (digits.length <= 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
  };

  const formatZipCode = (value: string) => {
    const digits = normalizeDigits(value).slice(0, 8);
    if (digits.length <= 5) return digits;
    return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  };

  useEffect(() => {
    if (deliveryType !== "ENTREGA") return;
    const cep = normalizeDigits(address.zip);
    if (cep.length !== 8) return;

    let cancelled = false;
    const resolveCep = async () => {
      try {
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        if (!response.ok) return;
        const payload = (await response.json()) as {
          erro?: boolean;
          logradouro?: string;
          bairro?: string;
          localidade?: string;
          uf?: string;
        };
        if (payload.erro) return;
        if (cancelled) return;
        setAddress((prev) => ({
          ...prev,
          street: payload.logradouro || prev.street,
          district: payload.bairro || prev.district,
          city: payload.localidade || prev.city,
          state: (payload.uf || prev.state || "SP").slice(0, 2).toUpperCase(),
        }));
      } catch {
        // CEP opcionalmente pode falhar sem bloquear checkout.
      }
    };

    resolveCep();
    return () => {
      cancelled = true;
    };
  }, [address.zip, deliveryType]);

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const deliveryAddress =
        deliveryType === "ENTREGA"
          ? {
              zip: address.zip.trim(),
              street: address.street.trim(),
              number: address.number.trim(),
              complement: address.complement.trim(),
              neighborhood: address.district.trim(),
              city: address.city.trim(),
              state: (address.state.trim() || "SP").slice(0, 2).toUpperCase(),
              reference: address.reference.trim(),
            }
          : {
              zip: "",
              street: "",
              number: "",
              complement: "",
              neighborhood: "",
              city: "",
              state: "",
              reference: "",
            };
      const normalizedOrderType =
        deliveryType === "RETIRADA" ? "pickup" : deliveryType === "MESA" ? "table" : "delivery";
      const parsedChangeFor = parseFloat(changeFor);
      const hasValidChangeFor = paymentMethod === "money" && changeFor && Number.isFinite(parsedChangeFor);

      const payload = {
        store_id: menuQuery.data?.tenant_id,
        items: cart.map((entry) => ({
          item_id: entry.item.id,
          quantity: entry.quantity,
          selected_modifiers: entry.selected_modifiers.map((mod) => ({ group_id: mod.group_id, option_id: mod.option_id })),
        })),
        customer_name: customerName,
        customer_phone: customerPhone,
        order_type: normalizedOrderType,
        delivery_address: deliveryAddress,
        street: deliveryType === "ENTREGA" ? address.street.trim() : "",
        number: deliveryType === "ENTREGA" ? address.number.trim() : "",
        complement: deliveryType === "ENTREGA" ? address.complement.trim() : "",
        neighborhood: deliveryType === "ENTREGA" ? address.district.trim() : "",
        city: deliveryType === "ENTREGA" ? address.city.trim() : "",
        state: deliveryType === "ENTREGA" ? (address.state.trim() || "SP").slice(0, 2).toUpperCase() : "",
        reference: deliveryType === "ENTREGA" ? address.reference.trim() : "",
        payment_method: paymentMethod,
        payment_change_for: hasValidChangeFor ? String(parsedChangeFor) : "",
        notes,
        delivery_type: deliveryType,
        table_number: deliveryType === "MESA" ? tableNumber.trim() : "",
      };

      return submitPublicOrder<CreateOrderResponse>(payload, slug);
    },
  });

  const parseCurrencyToCents = (value: string | number | null | undefined) => {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Math.round(value < 1000 ? value * 100 : value);
    }
    if (typeof value === "string") {
      const normalized = Number(value.replace(/\./g, "").replace(",", "."));
      if (Number.isFinite(normalized)) {
        return Math.round(normalized < 1000 ? normalized * 100 : normalized);
      }
    }
    return summaryTotalCents;
  };

  const validateCheckoutForm = () => {
    const nextErrors: CheckoutErrors = {};
    if (normalizeDigits(customerPhone).length < 10) nextErrors.customerPhone = "Informe um telefone válido";
    if (deliveryType === "ENTREGA") {
      if (normalizeDigits(address.zip).length !== 8) nextErrors.zip = "Informe o CEP";
      if (address.street.trim().length === 0) nextErrors.street = "Informe a rua";
      if (address.number.trim().length === 0) nextErrors.number = "Informe o número";
      if (address.district.trim().length === 0) nextErrors.district = "Informe o bairro";
      if (address.city.trim().length === 0) nextErrors.city = "Informe a cidade";
      if (address.state.trim().length === 0) nextErrors.state = "Informe o estado";
    }
    if (deliveryType === "MESA" && tableNumber.trim().length === 0) nextErrors.tableNumber = "Informe o número da mesa";
    if (paymentMethod === "money" && changeFor.trim().length === 0) nextErrors.changeFor = "Informe o troco";
    setCheckoutErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const createOrder = async () => {
    setCheckoutStep("submitting");
    setCheckoutMessage(null);
    try {
      const data = await checkoutMutation.mutateAsync();
      const orderId = data.daily_order_number ?? data.order_number ?? data.order_id ?? data.id ?? null;
      setCreatedOrderId(orderId);
      setCheckoutMessage(orderId ? `Pedido enviado! Número: #${orderId}` : "Pedido enviado com sucesso!");
      setCheckoutStep("success");
      setOrderSuccessData({
        order_id: orderId,
        points_earned: data.points_earned || 0,
        estimated_time: String(data.estimated_time ?? "30-45 min"),
        total: parseCurrencyToCents(data.total),
        items: cart,
      });
      setCart([]);
      window.localStorage.removeItem(cartStorageKey);
      window.localStorage.setItem(cartStorageKey, JSON.stringify([]));
      setNotes("");
      setChangeFor("");
      setTableNumber("");
      setCouponCode("");
      setCouponFeedback(null);
      setAppliedCouponId(null);
      setIsCouponApplied(false);
      setDiscountAmountCents(0);
      setNewTotalCents(0);
      setCheckoutErrors({});
    } catch {
      setCheckoutStep("payment");
      setCheckoutMessage("Não foi possível enviar o pedido.");
      setOrderSuccessData(null);
    }
  };

  const handleCheckoutContinue = async () => {
    if (checkoutStep === "cart") {
      setCheckoutStep("identify");
      return;
    }
    if (checkoutStep === "identify") {
      const normalizedPhone = normalizeDigits(customerPhone);
      if (normalizedPhone.length < 10) {
        setCheckoutErrors((prev) => ({ ...prev, customerPhone: "Informe um telefone válido" }));
        return;
      }
      setIsIdentifyingCustomer(true);
      setIdentifyError(null);
      try {
        if (customerProfile?.phone?.replace(/\D/g, "") === normalizedPhone) {
          setCustomerId(customerProfile.id);
          setCustomerName((prev) => prev || customerProfile?.name || "");
          setCustomerPhone(formatPhone(customerProfile.phone || normalizedPhone));
          window.localStorage.setItem(`storefront-customer:${slug}`, JSON.stringify(customerProfile));
          setCheckoutStep("returning");
        } else {
          setCheckoutStep("new-customer");
        }
      } finally {
        setIsIdentifyingCustomer(false);
      }
      return;
    }
    if (checkoutStep === "new-customer" || checkoutStep === "returning") {
      setCheckoutStep("payment");
      return;
    }
    if (checkoutStep === "payment") {
      if (!validateCheckoutForm()) return;
      await createOrder();
    }
  };

  const totalCents = useMemo(
    () =>
      cart.reduce((total, entry) => total + (entry.item.price_cents + entry.selected_modifiers.reduce((acc, mod) => acc + mod.price_cents, 0)) * entry.quantity, 0),
    [cart]
  );

  const summaryTotalCents = isCouponApplied ? newTotalCents : totalCents;

  const applyCouponMutation = useMutation({
    mutationFn: async () => {
      throw new Error("Validação de cupom indisponível no checkout público");
    },
    onError: () => {
      setCouponFeedback({ type: "error", text: "Validação de cupom indisponível no checkout público." });
      setAppliedCouponId(null);
      setIsCouponApplied(false);
      setDiscountAmountCents(0);
      setNewTotalCents(0);
    },
  });

  const handleRemoveCoupon = () => {
    setAppliedCouponId(null);
    setIsCouponApplied(false);
    setDiscountAmountCents(0);
    setNewTotalCents(0);
    setCouponFeedback(null);
  };


  const getGroupMinRequired = (group: ModifierGroup) => {
    if (typeof group.min_required === "number") return Math.max(group.min_required, 0);
    if (group.required) return Math.max(group.min_selection, 1);
    return Math.max(group.min_selection, 0);
  };

  const openSheet = (item: PublicMenuItem) => {
    const defaults: Record<number, number[]> = {};
    (item.modifier_groups || []).forEach((group) => {
      defaults[group.id] = group.options.filter((option) => option.is_default).map((option) => option.id);
    });
    setSelectedModifiers(defaults);
    setSheetItem(item);
  };

  const handleAddItem = (item: PublicMenuItem, modifiers: Array<{ group_id: number; option_id: number; name: string; price_cents: number }>) => {
    setCart((prev) => {
      const signature = JSON.stringify(modifiers.map((mod) => `${mod.group_id}:${mod.option_id}`).sort());
      const existing = prev.find((entry) => entry.item.id === item.id && JSON.stringify(entry.selected_modifiers.map((mod) => `${mod.group_id}:${mod.option_id}`).sort()) === signature);
      if (existing) {
        return prev.map((entry) =>
          entry.item.id === item.id && JSON.stringify(entry.selected_modifiers.map((mod) => `${mod.group_id}:${mod.option_id}`).sort()) === signature
            ? { ...entry, quantity: entry.quantity + 1 }
            : entry
        );
      }
      return [...prev, { item, quantity: 1, selected_modifiers: modifiers }];
    });
    setSheetItem(null);
  };

  const handleRemoveItem = (itemId: number) => {
    setCart((prev) => prev.map((entry) => (entry.item.id === itemId ? { ...entry, quantity: entry.quantity - 1 } : entry)).filter((entry) => entry.quantity > 0));
  };

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(cartStorageKey);
      if (stored) {
        const parsed = JSON.parse(stored) as CartItem[];
        if (Array.isArray(parsed)) setCart(parsed);
      }
    } catch {
      // Ignora erro de parse para não quebrar o checkout.
    } finally {
      setIsCartStorageReady(true);
    }
  }, [cartStorageKey]);

  useEffect(() => {
    if (!isCartStorageReady) return;
    window.localStorage.setItem(cartStorageKey, JSON.stringify(cart));
  }, [cart, cartStorageKey, isCartStorageReady]);

  if (menuQuery.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (menuQuery.isError || !menuQuery.data) {
    return <div className="p-6 text-sm text-red-600">Não foi possível carregar o cardápio.</div>;
  }

  const menu = menuQuery.data;
  const canSubmitCheckout = cart.length > 0 && checkoutStep !== "submitting";

  const sheetModifierGroups = (sheetItem?.modifier_groups || []).slice().sort((a, b) => a.order_index - b.order_index);
  const sheetValidationByGroup: Record<number, string> = {};
  sheetModifierGroups.forEach((group) => {
    const minRequired = getGroupMinRequired(group);
    const selectedCount = (selectedModifiers[group.id] || []).length;
    if (minRequired > 0 && selectedCount < minRequired) {
      sheetValidationByGroup[group.id] = `Selecione pelo menos ${minRequired} opções em ${group.name}`;
    }
  });
  const isSheetValid = Object.keys(sheetValidationByGroup).length === 0;
  const selectedSheetModifiers = sheetModifierGroups.flatMap((group) => {
    const selectedIds = selectedModifiers[group.id] || [];
    const activeOptions = group.options.filter((option) => option.is_active && selectedIds.includes(option.id));
    const maxSelection = group.max_selection > 0 ? group.max_selection : activeOptions.length;
    return activeOptions.slice(0, maxSelection).map((option) => ({
      group_id: group.id,
      option_id: option.id,
      name: option.name,
      price_cents: Math.round((Number(option.price_delta) || 0) * 100),
    }));
  });

  return (
    <>
      <div className="min-h-screen bg-slate-50 pb-32">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white p-4">
          <h1 className="text-lg font-semibold text-slate-900">Cardápio</h1>
          <p className="text-xs text-slate-500">Loja: {menu.slug}</p>
        </header>

        <main className="space-y-6 p-4">
          {menu.categories.map((category) => (
            <section key={category.id} className="space-y-3">
              <h2 className="text-base font-semibold text-slate-800">{category.name}</h2>
              <div className="grid gap-3">
                {category.items.map((item) => (
                  <Card key={item.id}>
                    <CardContent className="flex gap-3 p-4">
                      {item.image_url && <img src={item.image_url} alt={item.name} className="h-16 w-16 rounded-md object-cover" />}
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                        {item.description && <p className="text-xs text-slate-500">{item.description}</p>}
                        <p className="text-sm font-medium text-slate-700">R$ {(item.price_cents / 100).toFixed(2)}</p>
                      </div>
                      <Button size="sm" onClick={() => openSheet(item)}>
                        Adicionar
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          ))}

          {menu.items_without_category.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-base font-semibold text-slate-800">Outros</h2>
              <div className="grid gap-3">
                {menu.items_without_category.map((item) => (
                  <Card key={item.id}>
                    <CardContent className="flex gap-3 p-4">
                      {item.image_url && <img src={item.image_url} alt={item.name} className="h-16 w-16 rounded-md object-cover" />}
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                        {item.description && <p className="text-xs text-slate-500">{item.description}</p>}
                        <p className="text-sm font-medium text-slate-700">R$ {(item.price_cents / 100).toFixed(2)}</p>
                      </div>
                      <Button size="sm" onClick={() => openSheet(item)}>
                        Adicionar
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          )}

          <Card>
            <CardContent className="space-y-4 p-4">
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-sm font-medium text-slate-800">Carrinho</p>
                {cart.length === 0 && <p className="text-xs text-slate-500">Nenhum item no carrinho.</p>}
                {cart.length > 0 && (
                  <ul className="mt-2 space-y-2 text-sm">
                    {cart.map((entry) => (
                      <li key={`${entry.item.id}-${entry.selected_modifiers.map((mod) => mod.option_id).join("-")}`} className="flex items-center justify-between gap-2">
                        <span>
                          {entry.quantity}x {entry.item.name}
                          {entry.selected_modifiers.length > 0 ? ` (${entry.selected_modifiers.map((mod) => mod.name).join(", ")})` : ""}
                        </span>
                        <div className="flex items-center gap-2">
                          <span>
                            R$ {(((entry.item.price_cents + entry.selected_modifiers.reduce((acc, mod) => acc + mod.price_cents, 0)) * entry.quantity) / 100).toFixed(2)}
                          </span>
                          <Button variant="ghost" size="sm" onClick={() => handleRemoveItem(entry.item.id)}>
                            Remover
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 text-sm font-semibold text-slate-900">Total: R$ {(totalCents / 100).toFixed(2)}</p>
              </div>

              {checkoutMessage && <p className="rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-700">{checkoutMessage}</p>}

              <Button className="w-full" onClick={() => setIsCheckoutOpen(true)} disabled={cart.length === 0}>
                Finalizar pedido
              </Button>
            </CardContent>
          </Card>
        </main>
      </div>

      <CheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        cartItems={cart.map((entry) => ({
          id: entry.item.id,
          name: entry.item.name,
          price: (entry.item.price_cents + entry.selected_modifiers.reduce((acc, mod) => acc + mod.price_cents, 0)) / 100,
          quantity: entry.quantity,
          modifiers: entry.selected_modifiers.map((mod) => mod.name),
          selected_modifiers: entry.selected_modifiers,
        }))}
        onOrderSuccess={() => {
          setCart([]);
          setIsCheckoutOpen(false);
        }}
        tenant={{ slug, store_id: menu.tenant_id, name: menu.slug, delivery_fee: menu.tenant?.delivery_fee ?? 0 }}
        theme="white"
      />

      {sheetItem && (
        <div className="fixed inset-0 z-50 bg-black/50">
          <div className="absolute inset-0 overflow-auto bg-white p-4">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{sheetItem.name}</h2>
              <Button variant="ghost" onClick={() => setSheetItem(null)}>
                Fechar
              </Button>
            </div>
            {sheetModifierGroups.map((group) => (
                <div key={group.id} className="mb-4 rounded border p-3">
                  <p className="font-medium">
                    {group.name} {getGroupMinRequired(group) > 0 ? "*" : ""}
                  </p>
                  {group.description && <p className="text-xs text-slate-500">{group.description}</p>}
                  {group.options
                    .filter((o) => o.is_active)
                    .sort((a, b) => a.order_index - b.order_index)
                    .map((option) => {
                      const current = selectedModifiers[group.id] || [];
                      const checked = current.includes(option.id);
                      const inputType = group.max_selection === 1 ? "radio" : "checkbox";
                      return (
                        <label key={option.id} className="mt-2 flex items-center gap-2 text-sm">
                          <input
                            type={inputType}
                            checked={checked}
                            onChange={() => {
                              setSelectedModifiers((prev) => {
                                const existing = prev[group.id] || [];
                                if (group.max_selection === 1) {
                                  return { ...prev, [group.id]: [option.id] };
                                }
                                if (existing.includes(option.id)) {
                                  return { ...prev, [group.id]: existing.filter((id) => id !== option.id) };
                                }
                                if (existing.length >= group.max_selection) return prev;
                                return { ...prev, [group.id]: [...existing, option.id] };
                              });
                            }}
                          />
                          <span>
                            {option.name} (+R$ {(Number(option.price_delta) || 0).toFixed(2)})
                          </span>
                        </label>
                      );
                    })}
                  {sheetValidationByGroup[group.id] ? <p className="mt-2 text-xs text-red-600">{sheetValidationByGroup[group.id]}</p> : null}
                </div>
              ))}
            <Button
              className="w-full"
              disabled={!isSheetValid}
              onClick={() => {
                if (!isSheetValid) return;
                handleAddItem(sheetItem, selectedSheetModifiers);
              }}
            >
              Adicionar ao carrinho
            </Button>
          </div>
        </div>
      )}

      <style jsx global>{`
        @keyframes order-check-scale-in {
          0% {
            opacity: 0;
            transform: scale(0.4);
          }
          70% {
            opacity: 1;
            transform: scale(1.12);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }

        .order-success-check {
          width: 78px;
          height: 78px;
          border-radius: 999px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #10b981, #059669);
          color: #ffffff;
          font-size: 38px;
          font-weight: 800;
          box-shadow: 0 18px 35px rgba(16, 185, 129, 0.24);
          animation: order-check-scale-in 0.5s ease-out both;
        }
      `}</style>
    </>
  );
}
