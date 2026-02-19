"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardContent } from "@/components/ui/card";
import { baseUrl } from "@/lib/api";

interface PublicMenuItem {
  id: number;
  name: string;
  description?: string | null;
  price_cents: number;
}

interface PublicMenuCategory {
  id: number;
  name: string;
  items: PublicMenuItem[];
}

interface PublicMenuResponse {
  tenant: { name: string };
  categories: PublicMenuCategory[];
}

export default function StorefrontPage() {
  const menuQuery = useQuery({
    queryKey: ["public-menu"],
    queryFn: async () => {
      const response = await fetch(`${baseUrl}/public/menu`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Falha ao carregar cardápio");
      }
      return (await response.json()) as PublicMenuResponse;
    },
  });

  if (menuQuery.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (menuQuery.isError || !menuQuery.data) {
    return <p className="p-6 text-sm text-red-600">Não foi possível carregar o cardápio.</p>;
  }

  return (
    <main className="min-h-screen space-y-4 bg-slate-50 p-4">
      <h1 className="text-xl font-semibold text-slate-900">{menuQuery.data.tenant.name}</h1>
      {menuQuery.data.categories.map((category) => (
        <section key={category.id} className="space-y-2">
          <h2 className="text-sm font-semibold text-slate-700">{category.name}</h2>
          <div className="grid gap-2">
            {category.items.map((item) => (
              <Card key={item.id}>
                <CardContent className="p-3">
                  <p className="text-sm font-medium text-slate-900">{item.name}</p>
                  {item.description ? (
                    <p className="text-xs text-slate-500">{item.description}</p>
                  ) : null}
                  <p className="text-sm text-slate-700">R$ {(item.price_cents / 100).toFixed(2)}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
