"use client";

import { CSSProperties, useEffect, useMemo, useState } from "react";

import { StorefrontCategoryTabs } from "@/components/storefront/StorefrontCategoryTabs";
import { StorefrontHero } from "@/components/storefront/StorefrontHero";
import { formatPrice, StorefrontProductCard } from "@/components/storefront/StorefrontProductCard";
import { CartItem, ModifierGroupResponse, PublicMenuCategory, PublicMenuItem, PublicMenuResponse } from "@/components/storefront/types";
import { getStoreTheme } from "@/lib/storeTheme";

let checkoutStep = "review";
type DeliveryType = "ENTREGA" | "RETIRADA" | "MESA";

type CheckoutAddress = {
  zip: string;
  street: string;
  number: string;
  complement: string;
  district: string;
  city: string;
  reference: string;
};

interface StorefrontMenuContentProps {
  menu: PublicMenuResponse;
  enableCart?: boolean;
}

const getGroupMinRequired = (group: ModifierGroupResponse) => {
  if (typeof group.min_required === "number") {
    return Math.max(group.min_required, 0);
  }
  if (group.required) {
    return Math.max(group.min_selection, 1);
  }
  return Math.max(group.min_selection, 0);
};

export function StorefrontMenuContent({ menu, enableCart = true }: StorefrontMenuContentProps) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [isCartStorageReady, setIsCartStorageReady] = useState(false);
  const [activeCategoryId, setActiveCategoryId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [justAddedId, setJustAddedId] = useState<number | null>(null);
  const [configuratorItem, setConfiguratorItem] = useState<PublicMenuItem | null>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<number, number[]>>({});
  const [checkoutStepState, setCheckoutStepState] = useState<"review" | "form" | "submitting" | "success">("review");
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [deliveryType, setDeliveryType] = useState<DeliveryType>("ENTREGA");
  const [address, setAddress] = useState<CheckoutAddress>({ zip: "", street: "", number: "", complement: "", district: "", city: "", reference: "" });
  const [tableNumber, setTableNumber] = useState("");
  const [commandNumber, setCommandNumber] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("pix");
  const [changeFor, setChangeFor] = useState("");
  const [notes, setNotes] = useState("");
  const [orderProtocol, setOrderProtocol] = useState<string | null>(null);
  const [checkoutFormStep, setCheckoutFormStep] = useState<1 | 2 | 3 | 4>(1);
  const isPreview = typeof window !== "undefined" && window.location.pathname.includes("storefront-preview");
  const cartStorageKey = useMemo(() => `storefront-cart:${menu.slug}`, [menu.slug]);

  const theme = getStoreTheme(menu.public_settings);

  const customAccent = /^#([0-9A-Fa-f]{3}){1,2}$/.test(theme.primaryColor) ? theme.primaryColor : null;
  const rootStyle = (customAccent
    ? {
        "--accent": customAccent,
        "--accent-d": customAccent,
      }
    : undefined) as CSSProperties | undefined;

  const filteredCategories = useMemo<PublicMenuCategory[]>(() => {
    const query = search.trim().toLowerCase();
    return menu.categories
      .map((category) => ({
        ...category,
        items: category.items.filter((item) => {
          if (item.is_active === false) return false;
          if (!query) return true;
          return `${item.name} ${item.description ?? ""}`.toLowerCase().includes(query);
        }),
      }))
      .filter((category) => category.items.length > 0);
  }, [menu.categories, search]);

  const filteredUncategorizedItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    return menu.items_without_category.filter((item) => {
      if (item.is_active === false) return false;
      if (!query) return true;
      return `${item.name} ${item.description ?? ""}`.toLowerCase().includes(query);
    });
  }, [menu.items_without_category, search]);

  const categoriesForTabs = useMemo<PublicMenuCategory[]>(() => {
    if (!filteredUncategorizedItems.length) {
      return filteredCategories;
    }
    return [
      ...filteredCategories,
      {
        id: -1,
        name: "Sem categoria",
        emoji: "📦",
        sort_order: Number.MAX_SAFE_INTEGER,
        items: filteredUncategorizedItems,
      },
    ];
  }, [filteredCategories, filteredUncategorizedItems]);

  const visibleCategories = useMemo(() => {
    if (!activeCategoryId) {
      return categoriesForTabs;
    }
    return categoriesForTabs.filter((category) => String(category.id) === activeCategoryId);
  }, [activeCategoryId, categoriesForTabs]);

  const totalCents = useMemo(
    () =>
      cart.reduce((total, entry) => {
        const modifiersTotal = (entry.selected_modifiers ?? []).reduce((acc, mod) => acc + mod.price_cents, 0);
        return total + (entry.item.price_cents + modifiersTotal) * entry.quantity;
      }, 0),
    [cart]
  );
  const cartItemsCount = useMemo(() => cart.reduce((total, entry) => total + entry.quantity, 0), [cart]);

  useEffect(() => {
    if (!categoriesForTabs.length) {
      setActiveCategoryId("");
      return;
    }

    const hasActiveCategory = categoriesForTabs.some((category) => String(category.id) === activeCategoryId);
    if (!hasActiveCategory) {
      setActiveCategoryId(String(categoriesForTabs[0].id));
    }
  }, [activeCategoryId, categoriesForTabs]);

  const handleSelectCategory = (categoryId: string) => {
    if (categoryId === "storefront-cart") {
      document.getElementById("storefront-cart")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    setActiveCategoryId(categoryId);
    window.requestAnimationFrame(() => {
      document.getElementById(`sec-${categoryId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const openConfigurator = (item: PublicMenuItem) => {
    const defaults: Record<number, number[]> = {};
    (item.modifier_groups ?? []).forEach((group) => {
      defaults[group.id] = group.options.filter((option) => option.is_active && option.is_default).map((option) => option.id);
    });
    setSelectedModifiers(defaults);
    setConfiguratorItem(item);
  };

  const closeConfigurator = () => {
    setConfiguratorItem(null);
  };

  const closeCheckoutModal = () => {
    const modal = document.getElementById("checkoutModal");
    if (modal) {
      modal.style.display = "none";
    }
    checkoutStep = "review";
    setCheckoutStepState("review");
    setCheckoutFormStep(1);
    document.body.style.overflow = "";
  };

  const openCheckoutModal = () => {
    if (cart.length === 0) {
      setToast("Seu carrinho está vazio.");
      window.setTimeout(() => setToast(null), 2200);
      return;
    }

    const modal = document.getElementById("checkoutModal");
    if (!modal) return;

    checkoutStep = "review";
    setCheckoutStepState("review");
    setCheckoutFormStep(1);
    modal.style.display = "flex";
    document.body.style.overflow = "hidden";
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const buildOrderPayload = () => {
    const parsedChangeFor = parseFloat(changeFor);
    const hasValidChangeFor = paymentMethod === "money" && changeFor && Number.isFinite(parsedChangeFor);
    const deliveryAddress =
      deliveryType === "ENTREGA"
        ? {
            zip: address.zip.trim(),
            street: address.street.trim(),
            number: address.number.trim(),
            complement: address.complement.trim(),
            neighborhood: address.district.trim(),
            city: address.city.trim(),
            reference: address.reference.trim(),
          }
        : null;

    const normalizedOrderType =
      deliveryType === "RETIRADA" ? "pickup" : deliveryType === "MESA" ? "table" : "delivery";

    return {
      store_id: menu.tenant_id,
      customer_name: customerName,
      customer_phone: customerPhone,
      order_type: normalizedOrderType,
      delivery_type: deliveryType,
      delivery_address: deliveryAddress,
      street: deliveryType === "ENTREGA" ? address.street.trim() : "",
      number: deliveryType === "ENTREGA" ? address.number.trim() : "",
      complement: deliveryType === "ENTREGA" ? address.complement.trim() : "",
      neighborhood: deliveryType === "ENTREGA" ? address.district.trim() : "",
      city: deliveryType === "ENTREGA" ? address.city.trim() : "",
      reference: deliveryType === "ENTREGA" ? address.reference.trim() : "",
      table_number: deliveryType === "MESA" ? tableNumber.trim() : "",
      command_number: deliveryType === "MESA" ? commandNumber.trim() : "",
      payment_method: paymentMethod,
      payment_change_for: hasValidChangeFor ? String(parsedChangeFor) : "",
      notes,
      items: cart.map((entry) => ({
        item_id: entry.item.id,
        quantity: entry.quantity,
        selected_modifiers: (entry.selected_modifiers ?? []).map((modifier) => ({
          group_id: modifier.group_id,
          option_id: modifier.option_id,
        })),
      })),
    };
  };

  const renderSuccessScreen = (data: { order_id?: string | number; id?: string | number }) => {
    setOrderProtocol(String(data?.order_id ?? data?.id ?? ""));
    checkoutStep = "success";
    setCheckoutStepState("success");
  };

  const submitOrder = () => {
    checkoutStep = "submitting";
    setCheckoutStepState("submitting");

    const payload = buildOrderPayload();
    console.log("[checkout] submit payload", payload);

    fetch("/api/store/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.message ?? "Erro ao finalizar pedido");
        }
        renderSuccessScreen(data);
      })
      .catch(() => {
        alert("Erro ao finalizar pedido");
        checkoutStep = "form";
        setCheckoutStepState("form");
      });
  };

  const renderCheckoutForm = () => {
    checkoutStep = "form";
    setCheckoutStepState("form");
    setCheckoutFormStep(1);
  };

  const getNextCheckoutFormStep = (current: 1 | 2 | 3 | 4): 1 | 2 | 3 | 4 => {
    if (current === 2 && deliveryType !== "ENTREGA") {
      return 4;
    }
    return (Math.min(current + 1, 4) as 1 | 2 | 3 | 4);
  };

  const getPreviousCheckoutFormStep = (current: 1 | 2 | 3 | 4): 1 | 2 | 3 | 4 => {
    if (current === 4 && deliveryType !== "ENTREGA") {
      return 2;
    }
    return (Math.max(current - 1, 1) as 1 | 2 | 3 | 4);
  };

  function handleCheckoutContinue() {
    if (checkoutStep === "review") {
      renderCheckoutForm();
      return;
    }

    if (checkoutStep === "form") {
      if (checkoutFormStep < 4) {
        setCheckoutFormStep((prev) => getNextCheckoutFormStep(prev));
        return;
      }

      submitOrder();
    }
  }

  function handleCheckoutBack() {
    if (checkoutStep !== "form") return;
    setCheckoutFormStep((prev) => getPreviousCheckoutFormStep(prev));
  }

  const addConfiguredItemToCart = (item: PublicMenuItem, modifiers: Array<{ group_id: number; option_id: number; name: string; price_cents: number }>) => {
    setCart((prev) => {
      const signature = JSON.stringify(modifiers.map((mod) => `${mod.group_id}:${mod.option_id}`).sort());
      const existing = prev.find(
        (entry) =>
          entry.item.id === item.id &&
          JSON.stringify((entry.selected_modifiers ?? []).map((mod) => `${mod.group_id}:${mod.option_id}`).sort()) === signature
      );
      if (existing) {
        return prev.map((entry) =>
          entry.item.id === item.id &&
          JSON.stringify((entry.selected_modifiers ?? []).map((mod) => `${mod.group_id}:${mod.option_id}`).sort()) === signature
            ? { ...entry, quantity: entry.quantity + 1 }
            : entry
        );
      }
      return [...prev, { item, quantity: 1, selected_modifiers: modifiers }];
    });

    setJustAddedId(item.id);
    setToast(`${item.name} adicionado!`);
    window.setTimeout(() => setJustAddedId(null), 1200);
    window.setTimeout(() => setToast(null), 2200);
    closeConfigurator();
  };

  const getCartEntrySignature = (entry: CartItem) =>
    `${entry.item.id}::${(entry.selected_modifiers ?? [])
      .map((modifier) => `${modifier.group_id}:${modifier.option_id}`)
      .sort()
      .join("|")}`;

  const incrementCartItem = (targetEntry: CartItem) => {
    const targetSignature = getCartEntrySignature(targetEntry);
    setCart((prev) =>
      prev.map((entry) => (getCartEntrySignature(entry) === targetSignature ? { ...entry, quantity: entry.quantity + 1 } : entry))
    );
  };

  const decrementCartItem = (targetEntry: CartItem) => {
    const targetSignature = getCartEntrySignature(targetEntry);
    setCart((prev) =>
      prev.reduce<CartItem[]>((acc, entry) => {
        if (getCartEntrySignature(entry) !== targetSignature) {
          acc.push(entry);
          return acc;
        }

        if (entry.quantity > 1) {
          acc.push({ ...entry, quantity: entry.quantity - 1 });
        }
        return acc;
      }, [])
    );
  };

  const removeCartItem = (targetEntry: CartItem) => {
    const targetSignature = getCartEntrySignature(targetEntry);
    setCart((prev) => prev.filter((entry) => getCartEntrySignature(entry) !== targetSignature));
  };

  const activeModifierGroups = useMemo(
    () => (configuratorItem?.modifier_groups ?? []).map((group) => ({ ...group, options: group.options.filter((option) => option.is_active) })),
    [configuratorItem]
  );


  const validationByGroup = useMemo(() => {
    const result: Record<number, string> = {};
    activeModifierGroups.forEach((group) => {
      const minRequired = getGroupMinRequired(group);
      if (minRequired <= 0) return;
      const selectedCount = (selectedModifiers[group.id] ?? []).length;
      if (selectedCount < minRequired) {
        result[group.id] = `Selecione pelo menos ${minRequired} opções em ${group.name}`;
      }
    });
    return result;
  }, [activeModifierGroups, selectedModifiers]);

  function calculateTotal() {
    if (!configuratorItem) return 0;
    const modifiersTotal = activeModifierGroups.reduce((acc, group) => {
      const selectedIds = selectedModifiers[group.id] ?? [];
      return (
        acc +
        group.options.reduce((groupAcc, option) => {
          if (!selectedIds.includes(option.id)) return groupAcc;
          return groupAcc + Math.round((Number(option.price_delta) || 0) * 100);
        }, 0)
      );
    }, 0);
    return configuratorItem.price_cents + modifiersTotal;
  }

  const configuratorTotalCents = calculateTotal();
  const isConfiguratorValid = Object.keys(validationByGroup).length === 0;

  const selectedModifierPayload = useMemo(() => {
    if (!configuratorItem) return [] as Array<{ group_id: number; option_id: number; name: string; price_cents: number }>;
    return activeModifierGroups.flatMap((group) => {
      const selectedIds = selectedModifiers[group.id] ?? [];
      const selectedOptions = group.options.filter((option) => selectedIds.includes(option.id));
      const maxSelection = group.max_selection > 0 ? group.max_selection : selectedOptions.length;

      return selectedOptions.slice(0, maxSelection).map((option) => ({
        group_id: group.id,
        option_id: option.id,
        name: option.name,
        price_cents: Math.round((Number(option.price_delta) || 0) * 100),
      }));
    });
  }, [activeModifierGroups, configuratorItem, selectedModifiers]);

  useEffect(() => {
    const finalizeButton = document.getElementById("btn-finalizar");
    if (!finalizeButton) return;

    const onFinalizeClick = () => {
      openCheckoutModal();
    };

    finalizeButton.addEventListener("click", onFinalizeClick);

    return () => {
      finalizeButton.removeEventListener("click", onFinalizeClick);
    };
  }, [cart.length]);

  useEffect(() => {
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  useEffect(() => {
    if (!enableCart) return;

    try {
      const storedCart = window.localStorage.getItem(cartStorageKey);
      if (!storedCart) {
        setIsCartStorageReady(true);
        return;
      }

      const parsed = JSON.parse(storedCart) as CartItem[];
      if (Array.isArray(parsed)) {
        const sanitized = parsed.filter((entry) => entry?.item?.id && Number(entry.quantity) > 0);
        setCart(sanitized);
      }
    } catch {
      setCart([]);
    } finally {
      setIsCartStorageReady(true);
    }
  }, [cartStorageKey, enableCart]);

  useEffect(() => {
    if (!enableCart || !isCartStorageReady) return;
    window.localStorage.setItem(cartStorageKey, JSON.stringify(cart));
  }, [cart, cartStorageKey, enableCart, isCartStorageReady]);

  return (
    <div className="storefront-page min-h-screen" style={rootStyle}>
      <div className="store-card">
        <StorefrontHero
          store={{
            name: menu.tenant.name,
            subtitle: `@${menu.slug}${isPreview ? " • Prévia" : ""}`,
            logoUrl: theme.logoUrl,
            isOpen: menu.tenant.manual_open_status ?? true,
            waitTime: menu.tenant.estimated_prep_time ?? null,
            fee: "Grátis",
            rating: "4.9",
            totalReviews: "312",
          }}
          coverImageUrl={theme.coverImageUrl}
        />

        <div className="store-content">
          <StorefrontCategoryTabs
            categories={categoriesForTabs}
            activeCategoryId={activeCategoryId}
            onSelectCategory={handleSelectCategory}
            cartCount={enableCart ? cartItemsCount : 0}
          />

          <main className="page">
            <label className="search-wrap block">
              <span aria-hidden className="search-ico">
                🔍
              </span>
              <input
                aria-label="Buscar no cardápio"
                placeholder="Buscar por nome ou descrição..."
                className="search-input"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>

            {menu.promo_code && (
              <section className="promo" id="promo-banner">
                <div>
                  <div className="promo-label">🎉 Oferta especial</div>
                  <h3 className="promo-title">Promoção de hoje</h3>
                  <p className="promo-desc" id="promo-desc">
                    {menu.promo_description ?? ""}
                  </p>
                </div>
                <div className="promo-code-box">
                  <small>Use o código</small>
                  <strong id="promo-code">{menu.promo_code}</strong>
                </div>
              </section>
            )}

            <div id="categories-wrap">
              {visibleCategories.map((category) => (
                <section key={category.id} id={`sec-${category.id}`} className="scroll-mt-28 space-y-3">
                  <div className="section-head">
                    <h3 className="section-title">
                      <span>{category.emoji ?? "🍽️"}</span> {category.name}
                    </h3>
                    <span className="section-count">
                      {category.items.length} {category.items.length === 1 ? "item" : "itens"}
                    </span>
                  </div>
                  <div className="menu-list">
                    {category.items.map((item) => (
                      <StorefrontProductCard key={`${category.id}-${item.id}`} item={item} onAdd={enableCart ? openConfigurator : undefined} justAdded={justAddedId === item.id} />
                    ))}
                  </div>
                </section>
              ))}
            </div>

            {enableCart && (
              <section id="storefront-cart" className="cart-panel">
                <div className="cart-header">
                  <span style={{ fontSize: 19 }}>🛒</span>
                  <div className="cart-header-title">Seu carrinho</div>
                </div>
                <div id="cart-body">
                  {cart.length === 0 ? (
                    <div className="cart-empty">
                      <div className="cart-empty-ico">🛒</div>
                      <p>Nenhum item no carrinho.</p>
                      <small>Adicione itens do cardápio acima</small>
                    </div>
                  ) : (
                    <div className="cart-items-list">
                      {cart.map((entry) => {
                        const modifiersLabel = (entry.selected_modifiers ?? []).map((modifier) => modifier.name).join(", ");
                        const modifierTotal = (entry.selected_modifiers ?? []).reduce((acc, modifier) => acc + modifier.price_cents, 0);
                        return (
                          <div className="cart-row" key={`${entry.item.id}-${modifiersLabel || "simple"}`}>
                            <div className="cart-row-qty-wrap">
                              <button type="button" className="cart-row-qty-btn" aria-label={`Diminuir ${entry.item.name}`} onClick={() => decrementCartItem(entry)}>
                                −
                              </button>
                              <div className="cart-row-qty">{entry.quantity}x</div>
                              <button type="button" className="cart-row-qty-btn" aria-label={`Aumentar ${entry.item.name}`} onClick={() => incrementCartItem(entry)}>
                                +
                              </button>
                            </div>
                            <div className="cart-row-name">
                              {entry.item.name}
                              {modifiersLabel ? <small className="cart-row-modifiers">{modifiersLabel}</small> : null}
                            </div>
                            <div className="cart-row-actions">
                              <div className="cart-row-price">R$ {formatPrice((entry.item.price_cents + modifierTotal) * entry.quantity)}</div>
                              <button type="button" className="cart-row-remove" aria-label={`Remover ${entry.item.name}`} onClick={() => removeCartItem(entry)}>
                                Remover
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div className="cart-footer">
                  <div className="cart-total">
                    <span className="cart-total-label">Total do pedido</span>
                    <strong className="cart-total-value" id="cart-total">
                      R$ {formatPrice(totalCents)}
                    </strong>
                  </div>
                  <button type="button" id="btn-finalizar" className="btn-finalizar">
                    Finalizar Pedido
                  </button>
                </div>
              </section>
            )}
          </main>
        </div>
      </div>

      {enableCart && (
        <div
          id="checkoutModal"
          style={{ display: "none" }}
          className="fixed inset-0 z-[10001] items-start justify-center bg-slate-950/60 p-3 sm:p-4"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeCheckoutModal();
            }
          }}
        >
          <div className="flex h-[100dvh] w-full max-w-xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl sm:h-[92vh]">
            <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h3 className="text-base font-semibold text-slate-900">Checkout</h3>
              <button type="button" className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700" onClick={closeCheckoutModal}>
                Fechar
              </button>
            </header>

            <div className="flex-1 overflow-y-auto p-4">
              {checkoutStepState === "review" && (
                <>
                  <p className="text-sm text-slate-600">Revise seus itens antes de continuar.</p>

                  <div className="mt-4 space-y-2">
                    {cart.map((entry) => {
                      const modifiersLabel = (entry.selected_modifiers ?? []).map((modifier) => modifier.name).join(", ");
                      const modifierTotal = (entry.selected_modifiers ?? []).reduce((acc, modifier) => acc + modifier.price_cents, 0);
                      return (
                        <div key={`checkout-${entry.item.id}-${modifiersLabel || "simple"}`} className="rounded-lg border border-slate-200 p-3">
                          <div className="flex items-start justify-between gap-3 text-sm">
                            <div>
                              <p className="font-medium text-slate-900">
                                {entry.quantity}x {entry.item.name}
                              </p>
                              {modifiersLabel ? <p className="mt-1 text-xs text-slate-500">{modifiersLabel}</p> : null}
                            </div>
                            <p className="font-semibold text-slate-900">R$ {formatPrice((entry.item.price_cents + modifierTotal) * entry.quantity)}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              {checkoutStepState === "form" && (
                <div className="space-y-3">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    Etapa <strong>{checkoutFormStep}/4</strong>
                  </div>

                  <div key={`form-step-${checkoutFormStep}-${deliveryType}`} className="transition-all duration-300 ease-out animate-in fade-in-0 slide-in-from-right-1">
                    {checkoutFormStep === 1 && (
                      <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                        <p className="text-sm font-semibold text-slate-900">Dados de contato</p>
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Nome" value={customerName} onChange={(event) => setCustomerName(event.target.value)} />
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Telefone" value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} />
                      </div>
                    )}

                    {checkoutFormStep === 2 && (
                      <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                        <p className="text-sm font-semibold text-slate-900">Tipo do pedido</p>
                        <select className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={deliveryType} onChange={(event) => setDeliveryType(event.target.value as DeliveryType)}>
                          <option value="ENTREGA">Entrega</option>
                          <option value="RETIRADA">Retirada</option>
                          <option value="MESA">Mesa</option>
                        </select>
                        {deliveryType === "MESA" && (
                          <div className="space-y-2 pt-2">
                            <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Número da mesa" value={tableNumber} onChange={(event) => setTableNumber(event.target.value)} />
                            <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Número da comanda" value={commandNumber} onChange={(event) => setCommandNumber(event.target.value)} />
                          </div>
                        )}
                      </div>
                    )}

                    {checkoutFormStep === 3 && deliveryType === "ENTREGA" && (
                      <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                        <p className="text-sm font-semibold text-slate-900">Endereço de entrega</p>
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="CEP" value={address.zip} onChange={(event) => setAddress((prev) => ({ ...prev, zip: event.target.value }))} />
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Rua" value={address.street} onChange={(event) => setAddress((prev) => ({ ...prev, street: event.target.value }))} />
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Número" value={address.number} onChange={(event) => setAddress((prev) => ({ ...prev, number: event.target.value }))} />
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Complemento" value={address.complement} onChange={(event) => setAddress((prev) => ({ ...prev, complement: event.target.value }))} />
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Bairro" value={address.district} onChange={(event) => setAddress((prev) => ({ ...prev, district: event.target.value }))} />
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Cidade" value={address.city} onChange={(event) => setAddress((prev) => ({ ...prev, city: event.target.value }))} />
                        <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Referência" value={address.reference} onChange={(event) => setAddress((prev) => ({ ...prev, reference: event.target.value }))} />
                      </div>
                    )}

                    {checkoutFormStep === 4 && (
                      <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                        <p className="text-sm font-semibold text-slate-900">Pagamento e observações</p>
                        <select className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}>
                          <option value="pix">Forma de pagamento: Pix</option>
                          <option value="credit_card">Forma de pagamento: Cartão</option>
                          <option value="money">Forma de pagamento: Dinheiro</option>
                        </select>
                        {paymentMethod === "money" && (
                          <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Troco para" value={changeFor} onChange={(event) => setChangeFor(event.target.value)} />
                        )}
                        <textarea className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Observação" value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {checkoutStepState === "success" && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
                  Pedido enviado com sucesso{orderProtocol ? ` #${orderProtocol}` : ""}.
                </div>
              )}
            </div>

            <footer className="space-y-3 border-t border-slate-200 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">Total</span>
                <strong className="text-base text-slate-900">R$ {formatPrice(totalCents)}</strong>
              </div>
              {checkoutStepState !== "success" ? (
                <div className="flex gap-2">
                  {checkoutStepState === "form" && checkoutFormStep > 1 ? (
                    <button
                      type="button"
                      className="w-1/3 rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700"
                      onClick={handleCheckoutBack}
                    >
                      Voltar
                    </button>
                  ) : null}

                  <button
                    type="button"
                    id="checkoutContinueBtn"
                    className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white"
                    disabled={checkoutStepState === "submitting"}
                    onClick={handleCheckoutContinue}
                  >
                    {checkoutStepState === "submitting"
                      ? "Enviando..."
                      : checkoutStepState === "form" && checkoutFormStep === 4
                        ? "Finalizar pedido"
                        : "Continuar"}
                  </button>
                </div>
              ) : (
                <button type="button" className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white" onClick={closeCheckoutModal}>
                  Fechar
                </button>
              )}
            </footer>
          </div>
        </div>
      )}

      {enableCart && (
        <div
          id="productConfigurator"
          className={`product-configurator ${configuratorItem ? "open" : ""}`}
          aria-hidden={!configuratorItem}
          onClick={(event) => {
            if (event.target === event.currentTarget) closeConfigurator();
          }}
        >
          {configuratorItem && (
            <div className="product-configurator-sheet">
              <header className="product-configurator-header">
                <div>
                  <h3>{configuratorItem.name}</h3>
                  <p>Configure seus adicionais</p>
                </div>
                <button type="button" className="product-configurator-close" onClick={closeConfigurator} aria-label="Fechar configurador">
                  ✕
                </button>
              </header>

              <div className="product-configurator-body">
                {activeModifierGroups.map((group) => {
                  const current = selectedModifiers[group.id] || [];
                  const inputType = group.max_selection === 1 ? "radio" : "checkbox";
                  return (
                    <section key={group.id} className="configurator-group">
                      <div className="configurator-group-head">
                        <h4>{group.name}</h4>
                        {getGroupMinRequired(group) > 0 ? <span className="configurator-badge-required">Obrigatório</span> : null}
                      </div>
                      {group.description ? <p className="configurator-group-description">{group.description}</p> : null}
                      <div className="configurator-options">
                        {group.options.map((option) => {
                          const checked = current.includes(option.id);
                          return (
                            <label key={option.id} className="configurator-option-row">
                              <input
                                type={inputType}
                                name={`group-${group.id}`}
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
                              <span>{option.name}</span>
                              <strong>+ R$ {(Number(option.price_delta) || 0).toFixed(2).replace(".", ",")}</strong>
                            </label>
                          );
                        })}
                      </div>
                      {validationByGroup[group.id] ? <p className="configurator-validation-message">{validationByGroup[group.id]}</p> : null}
                    </section>
                  );
                })}
              </div>

              <footer className="product-configurator-footer">
                <div className="configurator-total-wrap">
                  <small>Total</small>
                  <strong>R$ {formatPrice(configuratorTotalCents)}</strong>
                </div>
                <button
                  type="button"
                  className="configurator-confirm-button"
                  disabled={!isConfiguratorValid}
                  onClick={() => {
                    if (!isConfiguratorValid) return;

                    const payload = {
                      item_id: configuratorItem.id,
                      quantity: 1,
                      selected_modifiers: selectedModifierPayload.map((modifier) => ({
                        group_id: modifier.group_id,
                        option_id: modifier.option_id,
                      })),
                    };
                    void payload;

                    addConfiguredItemToCart(configuratorItem, selectedModifierPayload);
                  }}
                >
                  Adicionar ao carrinho
                </button>
              </footer>
            </div>
          )}
        </div>
      )}

      <footer>
        Powered by <a href="#">Super SaaS Delivery</a> &nbsp;·&nbsp; © 2025
      </footer>

      <div className={`toast ${toast ? "show" : ""}`} id="toast">
        {toast ? `🛒 ${toast}` : ""}
      </div>
    </div>
  );
}
