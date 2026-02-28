"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { baseUrl } from "@/lib/api";

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
  categories: PublicMenuCategory[];
  items_without_category: PublicMenuItem[];
}

interface CartItem {
  item: PublicMenuItem;
  quantity: number;
  selected_modifiers: Array<{ group_id: number; option_id: number; name: string; price_cents: number }>;
}

interface DeliveryAddress {
  street: string;
  number: string;
  district: string;
  city: string;
}

interface CustomerLookupResponse {
  exists: boolean;
  name: string | null;
  customer_id?: number | null;
  address: (DeliveryAddress & { zip?: string; complement?: string }) | null;
}

interface ValidateCouponResponse {
  valid: boolean;
  discount_amount: number;
  new_total: number;
  message: string;
  coupon_id?: number | null;
}

export default function MobileHomePage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [cart, setCart] = useState<CartItem[]>([]);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [address, setAddress] = useState<DeliveryAddress>({ street: "", number: "", district: "", city: "" });
  const [notes, setNotes] = useState("");
  const [deliveryType, setDeliveryType] = useState("ENTREGA");
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

  const menuQuery = useQuery({
    queryKey: ["public-menu", slug],
    queryFn: async () => {
      const response = await fetch(`${baseUrl}/api/public/${slug}/menu`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Falha ao carregar cardápio");
      }
      return (await response.json()) as PublicMenuResponse;
    },
  });

  useEffect(() => {
    if (!menuQuery.data?.tenant_id || customerPhone.trim().length < 8) {
      return;
    }

    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          phone: customerPhone.trim(),
          tenant_id: String(menuQuery.data?.tenant_id),
        });
        const response = await fetch(`${baseUrl}/api/store/customer-by-phone?${params.toString()}`, {
          credentials: "include",
        });
        if (!response.ok) return;
        const payload = (await response.json()) as CustomerLookupResponse;
        if (!payload.exists) return;

        setCustomerId(payload.customer_id ?? null);

        if (payload.name) {
          setCustomerName((prev) => prev || payload.name || "");
        }

        if (payload.address) {
          setAddress((prev) => ({
            street: prev.street || payload.address?.street || "",
            number: prev.number || payload.address?.number || "",
            district: prev.district || payload.address?.district || "",
            city: prev.city || payload.address?.city || "",
          }));
        }
      } catch {
        // Sem bloqueio do checkout por falha de busca inteligente.
      }
    }, 500);

    return () => window.clearTimeout(timer);
  }, [customerPhone, menuQuery.data?.tenant_id]);

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const deliveryAddress = {
        street: address.street.trim(),
        number: address.number.trim(),
        district: address.district.trim(),
        city: address.city.trim(),
      };
      const flatAddress = `${deliveryAddress.street}, ${deliveryAddress.number} - ${deliveryAddress.district}, ${deliveryAddress.city}`;

      const response = await fetch(`${baseUrl}/api/public/${slug}/orders`, {
        credentials: "include",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: customerName,
          customer_phone: customerPhone,
          address: flatAddress,
          notes,
          order_note: notes,
          delivery_type: deliveryType,
          payment_method: paymentMethod,
          payment_change_for: paymentMethod === "money" ? changeFor : "",
          delivery_address: deliveryAddress,
          products: cart.map((entry) => ({
            product_id: entry.item.id,
            quantity: entry.quantity,
            selected_modifiers: entry.selected_modifiers.map((mod) => ({ group_id: mod.group_id, option_id: mod.option_id })),
          })),
          coupon_id: appliedCouponId,
        }),
      });
      if (!response.ok) {
        throw new Error("Não foi possível enviar o pedido");
      }
      return response.json() as Promise<{ order_id: number }>;
    },
    onSuccess: (data) => {
      setCheckoutMessage(`Pedido enviado! Número: #${data.order_id}`);
      setCart([]);
      setNotes("");
      setChangeFor("");
      setCouponCode("");
      setCouponFeedback(null);
      setAppliedCouponId(null);
      setIsCouponApplied(false);
      setDiscountAmountCents(0);
      setNewTotalCents(0);
      setIsCheckoutOpen(false);
    },
    onError: () => {
      setCheckoutMessage("Não foi possível enviar o pedido.");
    },
  });

  const totalCents = useMemo(
    () =>
      cart.reduce((total, entry) => total + (entry.item.price_cents + entry.selected_modifiers.reduce((acc, mod) => acc + mod.price_cents, 0)) * entry.quantity, 0),
    [cart]
  );

  const summaryTotalCents = isCouponApplied ? newTotalCents : totalCents;

  const applyCouponMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(`${baseUrl}/api/store/validate-coupon`, {
        credentials: "include",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: couponCode.trim(),
          order_total: totalCents / 100,
          customer_id: customerId,
        }),
      });

      if (!response.ok) {
        throw new Error("Não foi possível validar o cupom");
      }

      return (await response.json()) as ValidateCouponResponse;
    },
    onSuccess: (data) => {
      if (!data.valid) {
        setCouponFeedback({ type: "error", text: data.message || "Cupom inválido" });
        setAppliedCouponId(null);
        setIsCouponApplied(false);
        setDiscountAmountCents(0);
        setNewTotalCents(0);
        return;
      }

      setCouponFeedback({ type: "success", text: data.message || "Cupom aplicado com sucesso" });
      setAppliedCouponId(data.coupon_id ?? null);
      setIsCouponApplied(true);
      setDiscountAmountCents(Math.max(0, Math.round((data.discount_amount || 0) * 100)));
      setNewTotalCents(Math.max(0, Math.round((data.new_total || 0) * 100)));
    },
    onError: () => {
      setCouponFeedback({ type: "error", text: "Erro ao validar cupom. Tente novamente." });
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

  if (menuQuery.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (menuQuery.isError || !menuQuery.data) {
    return <div className="p-6 text-sm text-red-600">Não foi possível carregar o cardápio.</div>;
  }

  const menu = menuQuery.data;
  const canSubmitCheckout =
    customerPhone.trim().length > 0 &&
    address.street.trim().length > 0 &&
    address.number.trim().length > 0 &&
    address.district.trim().length > 0 &&
    address.city.trim().length > 0 &&
    cart.length > 0 &&
    !checkoutMutation.isPending;

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

      {isCheckoutOpen && (
        <div id="checkoutModal" className="fixed inset-0 z-50 bg-white">
          <header className="fixed inset-x-0 top-0 z-10 border-b border-slate-200 bg-white p-4">
            <div className="mx-auto flex w-full max-w-xl items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">Checkout</h2>
              <Button variant="ghost" onClick={() => setIsCheckoutOpen(false)}>
                Fechar
              </Button>
            </div>
          </header>

          <div className="h-screen overflow-y-auto px-4 pb-36 pt-20">
            <div className="mx-auto w-full max-w-xl space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Nome</label>
                <Input value={customerName} onChange={(event) => setCustomerName(event.target.value)} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Telefone *</label>
                <Input value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} required />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Rua *</label>
                <Input value={address.street} onChange={(event) => setAddress((prev) => ({ ...prev, street: event.target.value }))} required />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">Número *</label>
                  <Input value={address.number} onChange={(event) => setAddress((prev) => ({ ...prev, number: event.target.value }))} required />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">Bairro *</label>
                  <Input value={address.district} onChange={(event) => setAddress((prev) => ({ ...prev, district: event.target.value }))} required />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Cidade *</label>
                <Input value={address.city} onChange={(event) => setAddress((prev) => ({ ...prev, city: event.target.value }))} required />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Pagamento</label>
                <div className="space-y-2 rounded-md border border-slate-200 p-3">
                  {[
                    { label: "PIX", value: "pix" },
                    { label: "Dinheiro", value: "money" },
                    { label: "Cartão", value: "card" },
                  ].map((method) => (
                    <label key={method.value} className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="payment_method"
                        value={method.value}
                        checked={paymentMethod === method.value}
                        onChange={(event) => setPaymentMethod(event.target.value)}
                      />
                      <span>{method.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {paymentMethod === "money" && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">Troco para</label>
                  <Input value={changeFor} onChange={(event) => setChangeFor(event.target.value)} placeholder="Ex: 100,00" />
                </div>
              )}

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Observação</label>
                <textarea
                  className="min-h-[80px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Entrega</label>
                <select className="h-10 w-full rounded-md border border-slate-200 px-3 text-sm" value={deliveryType} onChange={(event) => setDeliveryType(event.target.value)}>
                  <option value="ENTREGA">Entrega</option>
                  <option value="RETIRADA">Retirada</option>
                </select>
              </div>

              <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-900">Cupom de desconto (opcional)</p>
                <div className="flex items-center gap-2">
                  <Input
                    id="couponCodeInput"
                    value={couponCode}
                    onChange={(event) => setCouponCode(event.target.value.toUpperCase())}
                    placeholder="Digite seu cupom"
                    disabled={applyCouponMutation.isPending || checkoutMutation.isPending}
                  />
                  <Button
                    id="applyCouponBtn"
                    type="button"
                    onClick={() => applyCouponMutation.mutate()}
                    disabled={applyCouponMutation.isPending || couponCode.trim().length === 0 || checkoutMutation.isPending}
                  >
                    {applyCouponMutation.isPending ? "Aplicando..." : "Aplicar"}
                  </Button>
                </div>

                {couponFeedback && (
                  <p className={`text-xs ${couponFeedback.type === "error" ? "text-red-600" : "text-emerald-700"}`}>{couponFeedback.text}</p>
                )}

                {isCouponApplied && (
                  <Button type="button" variant="ghost" className="h-auto p-0 text-red-600 hover:text-red-700" onClick={handleRemoveCoupon}>
                    Remover cupom
                  </Button>
                )}
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-900">Resumo final</p>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex items-center justify-between text-slate-600">
                    <span>Subtotal</span>
                    <span>R$ {(totalCents / 100).toFixed(2)}</span>
                  </div>
                  {isCouponApplied && (
                    <>
                      <div className="flex items-center justify-between text-emerald-700">
                        <span>Desconto</span>
                        <span>- R$ {(discountAmountCents / 100).toFixed(2)}</span>
                      </div>
                      <div className="flex items-center justify-between font-semibold text-slate-900">
                        <span>Total atualizado</span>
                        <span>R$ {(summaryTotalCents / 100).toFixed(2)}</span>
                      </div>
                    </>
                  )}
                  {!isCouponApplied && (
                    <div className="flex items-center justify-between font-semibold text-slate-900">
                      <span>Total</span>
                      <span>R$ {(totalCents / 100).toFixed(2)}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <footer className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white p-4">
            <div className="mx-auto flex w-full max-w-xl items-center justify-between gap-3">
              <p className="text-sm font-semibold text-slate-900">Total: R$ {(summaryTotalCents / 100).toFixed(2)}</p>
              <Button className="flex-1" onClick={() => checkoutMutation.mutate()} disabled={!canSubmitCheckout}>
                {checkoutMutation.isPending ? "Enviando..." : "Confirmar pedido"}
              </Button>
            </div>
          </footer>
        </div>
      )}

      {sheetItem && (
        <div className="fixed inset-0 z-50 bg-black/50">
          <div className="absolute inset-0 overflow-auto bg-white p-4">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{sheetItem.name}</h2>
              <Button variant="ghost" onClick={() => setSheetItem(null)}>
                Fechar
              </Button>
            </div>
            {(sheetItem.modifier_groups || [])
              .sort((a, b) => a.order_index - b.order_index)
              .map((group) => (
                <div key={group.id} className="mb-4 rounded border p-3">
                  <p className="font-medium">
                    {group.name} {group.required ? "*" : ""}
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
                </div>
              ))}
            <Button
              className="w-full"
              disabled={(sheetItem.modifier_groups || []).some((group) => group.required && (selectedModifiers[group.id] || []).length < Math.max(group.min_selection, 1))}
              onClick={() => {
                const allOptions = (sheetItem.modifier_groups || []).flatMap((group) =>
                  group.options.map((option) => ({ group_id: group.id, option_id: option.id, name: option.name, price_cents: Math.round((Number(option.price_delta) || 0) * 100) }))
                );
                const selected = allOptions.filter((entry) => (selectedModifiers[entry.group_id] || []).includes(entry.option_id));
                handleAddItem(sheetItem, selected);
              }}
            >
              Adicionar ao carrinho
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
