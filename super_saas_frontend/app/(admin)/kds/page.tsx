"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minimize2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface KdsItem {
  id: number;
  name: string;
  quantity: number;
  modifiers?: Array<{ name: string }>;
  production_area?: string;
}

interface KdsOrder {
  id: number;
  status: string;
  created_at: string;
  items: KdsItem[];
}

interface KdsOrderApi {
  id?: number;
  status?: string;
  created_at?: string;
  items?: unknown;
  itens?: unknown;
}

const toSafeModifiers = (value: unknown): Array<{ name: string }> => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((modifier) => {
      if (!modifier || typeof modifier !== "object") {
        return null;
      }

      const rawName = (modifier as { name?: unknown }).name;
      if (typeof rawName !== "string" || !rawName.trim()) {
        return null;
      }

      return { name: rawName };
    })
    .filter((modifier): modifier is { name: string } => Boolean(modifier));
};

const toSafeItems = (rawOrder: KdsOrderApi): KdsItem[] => {
  const rawItems = Array.isArray(rawOrder.items)
    ? rawOrder.items
    : Array.isArray(rawOrder.itens)
      ? rawOrder.itens
      : [];

  const items: KdsItem[] = [];

  rawItems.forEach((item) => {
    if (!item || typeof item !== "object") {
      return;
    }

    const itemData = item as {
      id?: unknown;
      name?: unknown;
      quantity?: unknown;
      production_area?: unknown;
      modifiers?: unknown;
    };

    items.push({
      id: Number(itemData.id) || 0,
      name: typeof itemData.name === "string" ? itemData.name : "Item sem nome",
      quantity: Number(itemData.quantity) || 0,
      production_area:
        typeof itemData.production_area === "string" ? itemData.production_area : undefined,
      modifiers: toSafeModifiers(itemData.modifiers),
    });
  });

  return items;
};

const normalizeKdsOrders = (response: unknown): KdsOrder[] => {
  if (!Array.isArray(response)) {
    return [];
  }

  return response
    .map((rawOrder) => {
      if (!rawOrder || typeof rawOrder !== "object") {
        return null;
      }

      const order = rawOrder as KdsOrderApi;

      return {
        id: Number(order.id) || 0,
        status: typeof order.status === "string" ? order.status : "PENDING",
        created_at: typeof order.created_at === "string" ? order.created_at : "",
        items: toSafeItems(order),
      };
    })
    .filter((order): order is KdsOrder => Boolean(order));
};

const areas = ["COZINHA", "BAR", "FRITURA", "DOCES"];

export default function KdsPage() {
  const queryClient = useQueryClient();
  const [area, setArea] = useState("COZINHA");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const kdsContainerRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["kds", area],
    queryFn: () =>
      api.get<unknown>(`/api/kds/orders?area=${area}`).then((response) => {
        console.log("[KDS] API response", response);
        return normalizeKdsOrders(response);
      }),
    refetchInterval: 5000,
  });

  const startMutation = useMutation({
    mutationFn: (orderId: number) =>
      api.post(`/api/kds/orders/${orderId}/start?area=${area}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kds", area] }),
  });

  const readyMutation = useMutation({
    mutationFn: (orderId: number) =>
      api.post(`/api/kds/orders/${orderId}/ready?area=${area}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kds", area] }),
  });

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === kdsContainerRef.current);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  const handleFullscreen = async () => {
    if (!kdsContainerRef.current) return;

    if (document.fullscreenElement === kdsContainerRef.current) {
      await document.exitFullscreen();
      return;
    }

    await kdsContainerRef.current.requestFullscreen();
  };

  return (
    <div
      ref={kdsContainerRef}
      className={cn(
        "space-y-6 rounded-xl transition-colors duration-200",
        isFullscreen && "min-h-screen bg-slate-950 p-6 text-slate-100"
      )}
    >
      <div
        className={cn(
          "flex flex-wrap items-center gap-3",
          isFullscreen &&
            "rounded-lg border border-slate-800 bg-slate-900/80 p-3 shadow-lg shadow-slate-950/40"
        )}
      >
        <Select
          value={area}
          onChange={(event) => setArea(event.target.value)}
          className={cn(
            isFullscreen &&
              "max-w-[220px] border-slate-600 bg-slate-950 text-slate-100 focus-visible:ring-slate-400"
          )}
        >
          {areas.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
        <Button
          variant="outline"
          onClick={handleFullscreen}
          className={cn(
            isFullscreen && "border-slate-600 bg-slate-800 text-slate-100 hover:bg-slate-700"
          )}
        >
          {isFullscreen ? (
            <>
              <Minimize2 className="mr-2 h-4 w-4" />
              Sair do modo KDS
            </>
          ) : (
            "Modo KDS"
          )}
        </Button>
        {isFullscreen && (
          <p className="text-xs text-slate-300">Pressione ESC para sair da tela cheia.</p>
        )}
      </div>

      {isLoading && <p className="text-sm text-slate-500">Carregando KDS...</p>}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
          Erro ao carregar pedidos do KDS.
        </div>
      )}

      {!isLoading && !isError && !data?.length && (
        <div
          className={cn(
            "rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-600",
            isFullscreen && "border-slate-700 bg-slate-900 text-slate-300"
          )}
        >
          Nenhum pedido pendente para a área <strong>{area}</strong> no momento.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data?.map((order) => (
          <Card
            key={order.id}
            className={cn(
              "border-l-4 border-l-brand-500",
              isFullscreen && "border-slate-700 bg-slate-900"
            )}
          >
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Pedido #{order.id}</CardTitle>
                <Badge variant="secondary">{order.status}</Badge>
              </div>
              <p className={cn("text-xs text-slate-500", isFullscreen && "text-slate-300")}>
                {new Date(order.created_at).toLocaleString("pt-BR")}
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              <ul className="space-y-2 text-sm">
                {(order.items ?? []).length === 0 && (
                  <li
                    className={cn(
                      "rounded-md border border-dashed border-slate-200 p-2 text-xs text-slate-500",
                      isFullscreen && "border-slate-700 text-slate-300"
                    )}
                  >
                    Pedido sem itens para exibir.
                  </li>
                )}
                {(order.items ?? []).map((item, index) => (
                  <li
                    key={`${item.id}-${item.name}-${index}`}
                    className={cn("rounded-md bg-slate-50 p-2", isFullscreen && "bg-slate-800")}
                  >
                    <div className="flex items-center justify-between">
                      <span>
                        {item.quantity}x {item.name}
                      </span>
                      {item.production_area && (
                        <Badge variant="outline">{item.production_area}</Badge>
                      )}
                    </div>
                    {(item.modifiers ?? []).length > 0 ? (
                      <p className={cn("text-xs text-slate-500", isFullscreen && "text-slate-300")}>
                        {(item.modifiers ?? []).map((mod) => mod.name).join(", ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => startMutation.mutate(order.id)}
                >
                  Iniciar
                </Button>
                <Button size="sm" onClick={() => readyMutation.mutate(order.id)}>
                  Finalizar
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
