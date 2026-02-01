"use client";

import { useEffect, useMemo, useState } from "react";

interface PublicMenuItem {
  id: number;
  category_id: number | null;
  name: string;
  description?: string | null;
  price_cents: number;
  image_url?: string | null;
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

interface CartEntry {
  item: PublicMenuItem;
  quantity: number;
}

interface CheckoutForm {
  customer_name: string;
  customer_phone: string;
  address: string;
  notes: string;
  delivery_type: string;
  payment_method: string;
}

const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

const buildApiUrl = (path: string) => {
  if (!apiBase) {
    return path;
  }
  return `${apiBase}${path}`;
};

const formatPrice = (valueCents: number) =>
  new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(valueCents / 100);

export default function PublicMenuPage({ params }: { params: { slug: string } }) {
  const [menu, setMenu] = useState<PublicMenuResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cart, setCart] = useState<Record<number, CartEntry>>({});
  const [form, setForm] = useState<CheckoutForm>({
    customer_name: "",
    customer_phone: "",
    address: "",
    notes: "",
    delivery_type: "",
    payment_method: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [orderId, setOrderId] = useState<number | null>(null);

  useEffect(() => {
    const fetchMenu = async () => {
      try {
        const host = window.location.host;
        const menuUrl = new URL(buildApiUrl("/public/menu"), window.location.origin);
        if (params.slug) {
          menuUrl.searchParams.set("slug", params.slug);
        }
        const response = await fetch(menuUrl.toString(), {
          headers: { "x-forwarded-host": host },
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error("Não foi possível carregar o cardápio.");
        }
        const data = (await response.json()) as PublicMenuResponse;
        setMenu(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Erro ao carregar cardápio.";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchMenu();
  }, []);

  const cartEntries = useMemo(() => Object.values(cart), [cart]);
  const cartTotal = useMemo(
    () => cartEntries.reduce((total, entry) => total + entry.item.price_cents * entry.quantity, 0),
    [cartEntries],
  );

  const updateQuantity = (item: PublicMenuItem, delta: number) => {
    setCart((prev) => {
      const current = prev[item.id];
      const nextQty = (current?.quantity || 0) + delta;
      if (nextQty <= 0) {
        const { [item.id]: _removed, ...rest } = prev;
        return rest;
      }
      return {
        ...prev,
        [item.id]: { item, quantity: nextQty },
      };
    });
  };

  const handleCheckoutChange = (field: keyof CheckoutForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    if (!cartEntries.length) {
      setError("Adicione itens ao carrinho antes de finalizar.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const host = window.location.host;
      const response = await fetch(buildApiUrl("/public/orders"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-forwarded-host": host,
        },
        body: JSON.stringify({
          ...form,
          items: cartEntries.map((entry) => ({
            item_id: entry.item.id,
            quantity: entry.quantity,
          })),
        }),
      });
      if (!response.ok) {
        throw new Error("Não foi possível concluir o pedido.");
      }
      const data = (await response.json()) as { order_id: number };
      setOrderId(data.order_id);
      setCart({});
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro ao enviar pedido.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-700">
        Carregando cardápio...
      </div>
    );
  }

  if (error && !menu) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-red-600">
        {error}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 lg:flex-row">
        <div className="flex-1 space-y-8">
          <header className="space-y-2">
            <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Cardápio</p>
            <h1 className="text-3xl font-semibold">{menu?.slug ?? "Restaurante"}</h1>
            <p className="text-slate-600">Escolha seus itens favoritos e finalize o pedido.</p>
          </header>

          {menu?.categories.map((category) => (
            <section key={category.id} className="space-y-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-800">{category.name}</h2>
                <p className="text-sm text-slate-500">Seleção do restaurante</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {category.items.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    {item.image_url ? (
                      <img
                        src={item.image_url}
                        alt={item.name}
                        className="mb-3 h-40 w-full rounded-xl object-cover"
                      />
                    ) : null}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-slate-900">{item.name}</h3>
                        <span className="text-sm font-semibold text-emerald-600">
                          {formatPrice(item.price_cents)}
                        </span>
                      </div>
                      {item.description ? (
                        <p className="text-sm text-slate-600">{item.description}</p>
                      ) : null}
                    </div>
                    <div className="mt-4 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-600"
                          onClick={() => updateQuantity(item, -1)}
                          type="button"
                        >
                          -
                        </button>
                        <span className="w-6 text-center text-sm font-medium text-slate-700">
                          {cart[item.id]?.quantity ?? 0}
                        </span>
                        <button
                          className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-600"
                          onClick={() => updateQuantity(item, 1)}
                          type="button"
                        >
                          +
                        </button>
                      </div>
                      <button
                        className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
                        onClick={() => updateQuantity(item, 1)}
                        type="button"
                      >
                        Adicionar
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}

          {menu?.items_without_category.length ? (
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-slate-800">Outros itens</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                {menu.items_without_category.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-slate-900">{item.name}</h3>
                        <span className="text-sm font-semibold text-emerald-600">
                          {formatPrice(item.price_cents)}
                        </span>
                      </div>
                      {item.description ? (
                        <p className="text-sm text-slate-600">{item.description}</p>
                      ) : null}
                    </div>
                    <div className="mt-4 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-600"
                          onClick={() => updateQuantity(item, -1)}
                          type="button"
                        >
                          -
                        </button>
                        <span className="w-6 text-center text-sm font-medium text-slate-700">
                          {cart[item.id]?.quantity ?? 0}
                        </span>
                        <button
                          className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-600"
                          onClick={() => updateQuantity(item, 1)}
                          type="button"
                        >
                          +
                        </button>
                      </div>
                      <button
                        className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
                        onClick={() => updateQuantity(item, 1)}
                        type="button"
                      >
                        Adicionar
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <aside className="w-full max-w-md shrink-0 space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:sticky lg:top-10">
          <div className="space-y-1">
            <h2 className="text-xl font-semibold text-slate-900">Seu carrinho</h2>
            <p className="text-sm text-slate-500">Confira os itens antes de finalizar.</p>
          </div>
          <div className="space-y-4">
            {cartEntries.length ? (
              cartEntries.map((entry) => (
                <div key={entry.item.id} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{entry.item.name}</p>
                    <p className="text-xs text-slate-500">
                      {entry.quantity} × {formatPrice(entry.item.price_cents)}
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-slate-900">
                    {formatPrice(entry.item.price_cents * entry.quantity)}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">Seu carrinho está vazio.</p>
            )}
          </div>

          <div className="flex items-center justify-between border-t border-slate-200 pt-4">
            <span className="text-sm font-semibold text-slate-600">Total</span>
            <span className="text-lg font-semibold text-slate-900">{formatPrice(cartTotal)}</span>
          </div>

          <div className="space-y-3">
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Seu nome"
              value={form.customer_name}
              onChange={(event) => handleCheckoutChange("customer_name", event.target.value)}
            />
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Telefone"
              value={form.customer_phone}
              onChange={(event) => handleCheckoutChange("customer_phone", event.target.value)}
            />
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Endereço"
              value={form.address}
              onChange={(event) => handleCheckoutChange("address", event.target.value)}
            />
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Tipo de entrega"
              value={form.delivery_type}
              onChange={(event) => handleCheckoutChange("delivery_type", event.target.value)}
            />
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Forma de pagamento"
              value={form.payment_method}
              onChange={(event) => handleCheckoutChange("payment_method", event.target.value)}
            />
            <textarea
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Observações"
              rows={3}
              value={form.notes}
              onChange={(event) => handleCheckoutChange("notes", event.target.value)}
            />
          </div>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {orderId ? (
            <p className="text-sm text-emerald-600">Pedido #{orderId} enviado com sucesso!</p>
          ) : null}

          <button
            className="w-full rounded-lg bg-emerald-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
            onClick={handleSubmit}
            disabled={submitting}
            type="button"
          >
            {submitting ? "Enviando..." : "Finalizar pedido"}
          </button>
        </aside>
      </div>
    </div>
  );
}
