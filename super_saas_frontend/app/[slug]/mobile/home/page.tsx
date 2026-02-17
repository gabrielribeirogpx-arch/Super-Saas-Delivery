"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { baseUrl } from "@/lib/api";

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

interface CartItem {
  item: PublicMenuItem;
  quantity: number;
}

export default function MobileHomePage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [cart, setCart] = useState<CartItem[]>([]);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [deliveryType, setDeliveryType] = useState("ENTREGA");
  const [paymentMethod, setPaymentMethod] = useState("PIX");
  const [checkoutMessage, setCheckoutMessage] = useState<string | null>(null);

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

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(`${baseUrl}/api/public/${slug}/orders`, {
        credentials: "include",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: customerName,
          customer_phone: customerPhone,
          address,
          notes,
          delivery_type: deliveryType,
          payment_method: paymentMethod,
          items: cart.map((entry) => ({
            item_id: entry.item.id,
            quantity: entry.quantity,
          })),
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
    },
    onError: () => {
      setCheckoutMessage("Não foi possível enviar o pedido.");
    },
  });

  const totalCents = useMemo(
    () =>
      cart.reduce(
        (total, entry) => total + entry.item.price_cents * entry.quantity,
        0
      ),
    [cart]
  );

  const handleAddItem = (item: PublicMenuItem) => {
    setCart((prev) => {
      const existing = prev.find((entry) => entry.item.id === item.id);
      if (existing) {
        return prev.map((entry) =>
          entry.item.id === item.id
            ? { ...entry, quantity: entry.quantity + 1 }
            : entry
        );
      }
      return [...prev, { item, quantity: 1 }];
    });
  };

  const handleRemoveItem = (itemId: number) => {
    setCart((prev) =>
      prev
        .map((entry) =>
          entry.item.id === itemId
            ? { ...entry, quantity: entry.quantity - 1 }
            : entry
        )
        .filter((entry) => entry.quantity > 0)
    );
  };

  if (menuQuery.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (menuQuery.isError || !menuQuery.data) {
    return (
      <div className="p-6 text-sm text-red-600">
        Não foi possível carregar o cardápio.
      </div>
    );
  }

  const menu = menuQuery.data;

  return (
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
                    {item.image_url && (
                      <img
                        src={item.image_url}
                        alt={item.name}
                        className="h-16 w-16 rounded-md object-cover"
                      />
                    )}
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                      {item.description && (
                        <p className="text-xs text-slate-500">{item.description}</p>
                      )}
                      <p className="text-sm font-medium text-slate-700">
                        R$ {(item.price_cents / 100).toFixed(2)}
                      </p>
                    </div>
                    <Button size="sm" onClick={() => handleAddItem(item)}>
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
                    {item.image_url && (
                      <img
                        src={item.image_url}
                        alt={item.name}
                        className="h-16 w-16 rounded-md object-cover"
                      />
                    )}
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                      {item.description && (
                        <p className="text-xs text-slate-500">{item.description}</p>
                      )}
                      <p className="text-sm font-medium text-slate-700">
                        R$ {(item.price_cents / 100).toFixed(2)}
                      </p>
                    </div>
                    <Button size="sm" onClick={() => handleAddItem(item)}>
                      Adicionar
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Checkout</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Nome</label>
              <Input value={customerName} onChange={(event) => setCustomerName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Telefone</label>
              <Input
                value={customerPhone}
                onChange={(event) => setCustomerPhone(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Endereço</label>
              <Input value={address} onChange={(event) => setAddress(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Observações</label>
              <textarea
                className="min-h-[80px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Entrega</label>
                <select
                  className="h-10 w-full rounded-md border border-slate-200 px-3 text-sm"
                  value={deliveryType}
                  onChange={(event) => setDeliveryType(event.target.value)}
                >
                  <option value="ENTREGA">Entrega</option>
                  <option value="RETIRADA">Retirada</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Pagamento</label>
                <select
                  className="h-10 w-full rounded-md border border-slate-200 px-3 text-sm"
                  value={paymentMethod}
                  onChange={(event) => setPaymentMethod(event.target.value)}
                >
                  <option value="PIX">Pix</option>
                  <option value="CARTAO">Cartão</option>
                  <option value="DINHEIRO">Dinheiro</option>
                </select>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-sm font-medium text-slate-800">Carrinho</p>
              {cart.length === 0 && (
                <p className="text-xs text-slate-500">Nenhum item no carrinho.</p>
              )}
              {cart.length > 0 && (
                <ul className="mt-2 space-y-2 text-sm">
                  {cart.map((entry) => (
                    <li key={entry.item.id} className="flex items-center justify-between">
                      <span>
                        {entry.quantity}x {entry.item.name}
                      </span>
                      <div className="flex items-center gap-2">
                        <span>
                          R$ {(entry.item.price_cents * entry.quantity / 100).toFixed(2)}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveItem(entry.item.id)}
                        >
                          Remover
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-sm font-semibold text-slate-900">
                Total: R$ {(totalCents / 100).toFixed(2)}
              </p>
            </div>

            {checkoutMessage && (
              <p className="rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-700">
                {checkoutMessage}
              </p>
            )}

            <Button
              className="w-full"
              onClick={() => checkoutMutation.mutate()}
              disabled={checkoutMutation.isPending || cart.length === 0}
            >
              {checkoutMutation.isPending ? "Enviando..." : "Enviar pedido"}
            </Button>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
