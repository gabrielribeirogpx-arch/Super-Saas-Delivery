"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardContent } from "@/components/ui/card";
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

interface PublicSettings {
  cover_image_url?: string | null;
  cover_video_url?: string | null;
  logo_url?: string | null;
  theme?: string | null;
  primary_color?: string | null;
}

interface PublicMenuResponse {
  tenant_id: number;
  slug: string;
  tenant: {
    id: number;
    slug: string;
    name: string;
    custom_domain?: string | null;
  };
  public_settings?: PublicSettings | null;
  categories: PublicMenuCategory[];
  items_without_category: PublicMenuItem[];
}

export default function PublicPreviewPage({ params }: { params: { slug: string } }) {
  const { slug } = params;

  const menuQuery = useQuery({
    queryKey: ["public-menu-preview", slug],
    queryFn: async () => {
      const response = await fetch(
        `${baseUrl}/public/menu`,
        { credentials: "include" }
      );
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
    return (
      <div className="p-6 text-sm text-red-600">
        Não foi possível carregar o cardápio.
      </div>
    );
  }

  const menu = menuQuery.data;
  const publicSettings = menu.public_settings ?? {};

  return (
    <div className="min-h-screen bg-slate-50 pb-16">
      <header className="relative">
        {publicSettings.cover_video_url ? (
          <video
            className="h-48 w-full object-cover sm:h-56"
            src={publicSettings.cover_video_url}
            autoPlay
            muted
            loop
            playsInline
          />
        ) : publicSettings.cover_image_url ? (
          <img
            className="h-48 w-full object-cover sm:h-56"
            src={publicSettings.cover_image_url}
            alt={`Capa ${menu.tenant.name}`}
          />
        ) : (
          <div className="flex h-48 w-full items-center justify-center bg-slate-900 text-slate-100">
            Sem capa configurada
          </div>
        )}

        <div className="absolute inset-x-0 bottom-0 flex items-center gap-3 bg-gradient-to-t from-black/70 to-transparent p-4 text-white">
          {publicSettings.logo_url && (
            <img
              src={publicSettings.logo_url}
              alt={`Logo ${menu.tenant.name}`}
              className="h-12 w-12 rounded-full border border-white object-cover"
            />
          )}
          <div>
            <p className="text-lg font-semibold">{menu.tenant.name}</p>
            <p className="text-xs">{menu.slug}</p>
          </div>
        </div>
      </header>

      <main className="space-y-6 p-4">
        {menu.categories.map((category) => (
          <section key={category.id} className="space-y-3">
            <h2 className="text-base font-semibold text-slate-800">
              {category.name}
            </h2>
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
                      <p className="text-sm font-semibold text-slate-900">
                        {item.name}
                      </p>
                      {item.description && (
                        <p className="text-xs text-slate-500">
                          {item.description}
                        </p>
                      )}
                      <p className="text-sm font-medium text-slate-700">
                        R$ {(item.price_cents / 100).toFixed(2)}
                      </p>
                    </div>
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
                      <p className="text-sm font-semibold text-slate-900">
                        {item.name}
                      </p>
                      {item.description && (
                        <p className="text-xs text-slate-500">
                          {item.description}
                        </p>
                      )}
                      <p className="text-sm font-medium text-slate-700">
                        R$ {(item.price_cents / 100).toFixed(2)}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
