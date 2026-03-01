"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Maximize2, Minimize2 } from "lucide-react";

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
  cliente_nome?: string;
  tipo_entrega?: string;
  observacao?: string;
  forma_pagamento?: string;
  ready_areas?: string[];
  items: KdsItem[];
}

interface KdsOrderApi {
  id?: number;
  status?: string;
  created_at?: string;
  cliente_nome?: unknown;
  tipo_entrega?: unknown;
  observacao?: unknown;
  order_note?: unknown;
  forma_pagamento?: unknown;
  payment_method?: unknown;
  ready_areas?: unknown;
  items?: unknown;
  itens?: unknown;
}

type KdsColumnKey = "pending" | "preparing" | "ready";

const KDS_COLUMNS: Array<{
  key: KdsColumnKey;
  title: string;
  description: string;
  tone: string;
}> = [
  {
    key: "pending",
    title: "PENDENTE",
    description: "Aguardando início",
    tone: "bg-slate-100 border-slate-200",
  },
  {
    key: "preparing",
    title: "EM PREPARO",
    description: "Sendo preparado",
    tone: "bg-amber-50 border-amber-200",
  },
  {
    key: "ready",
    title: "PRONTO",
    description: "Finalizado na área",
    tone: "bg-emerald-50 border-emerald-200",
  },
];

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
    .map((rawOrder): KdsOrder | null => {
      if (!rawOrder || typeof rawOrder !== "object") {
        return null;
      }

      const order = rawOrder as KdsOrderApi;

      return {
        id: Number(order.id) || 0,
        status: typeof order.status === "string" ? order.status : "PENDING",
        created_at: typeof order.created_at === "string" ? order.created_at : "",
        cliente_nome:
          typeof order.cliente_nome === "string" && order.cliente_nome.trim()
            ? order.cliente_nome
            : "Cliente não informado",
        tipo_entrega: typeof order.tipo_entrega === "string" ? order.tipo_entrega : "",
        observacao:
          typeof order.observacao === "string"
            ? order.observacao
            : typeof order.order_note === "string"
              ? order.order_note
              : "",
        forma_pagamento:
          typeof order.forma_pagamento === "string"
            ? order.forma_pagamento
            : typeof order.payment_method === "string"
              ? order.payment_method
              : "",
        ready_areas: Array.isArray(order.ready_areas)
          ? order.ready_areas
              .map((entry) => (typeof entry === "string" ? entry.toUpperCase().trim() : ""))
              .filter(Boolean)
          : [],
        items: toSafeItems(order),
      };
    })
    .filter((order): order is KdsOrder => Boolean(order));
};

const areas = ["COZINHA", "BAR", "FRITURA", "DOCES"];

export default function KdsPage() {
  const queryClient = useQueryClient();
  const [area, setArea] = useState("COZINHA");
  const [isTvMode, setIsTvMode] = useState(false);
  const [now, setNow] = useState(Date.now());
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
    const interval = window.setInterval(() => setNow(Date.now()), 30000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const active = document.fullscreenElement === kdsContainerRef.current;
      if (!active) {
        setIsTvMode(false);
      }
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  const formatOrderType = (type?: string) => {
    const normalized = (type || "").trim().toUpperCase();
    if (normalized.includes("ENTREGA")) return "ENTREGA";
    if (normalized.includes("RETIRADA")) return "RETIRADA";
    if (normalized.includes("MESA")) return "MESA";
    return "NÃO INFORMADO";
  };

  const getUrgency = (createdAt: string) => {
    const created = new Date(createdAt).getTime();
    const elapsedMin = Number.isNaN(created) ? 0 : Math.max(0, Math.floor((now - created) / 60000));

    if (elapsedMin >= 25) {
      return { elapsedMin, tone: "text-red-700 bg-red-100", pulse: true };
    }
    if (elapsedMin >= 15) {
      return { elapsedMin, tone: "text-red-700 bg-red-100", pulse: false };
    }
    if (elapsedMin >= 5) {
      return { elapsedMin, tone: "text-amber-700 bg-amber-100", pulse: false };
    }
    return { elapsedMin, tone: "text-emerald-700 bg-emerald-100", pulse: false };
  };

  const getOrderColumn = (order: KdsOrder): KdsColumnKey => {
    const status = order.status.toLowerCase();
    const isReadyInArea = (order.ready_areas ?? []).includes(area);

    if (status === "ready" || status === "pronto" || isReadyInArea) {
      return "ready";
    }
    if (status === "preparing" || status === "em_preparo" || status === "preparo") {
      return "preparing";
    }
    return "pending";
  };

  const ordersByColumn = useMemo(() => {
    const grouped: Record<KdsColumnKey, KdsOrder[]> = {
      pending: [],
      preparing: [],
      ready: [],
    };

    (data ?? []).forEach((order) => {
      grouped[getOrderColumn(order)].push(order);
    });

    return grouped;
  }, [data, area]);

  const toggleTvMode = async () => {
    if (!kdsContainerRef.current) return;

    if (isTvMode) {
      setIsTvMode(false);
      if (document.fullscreenElement === kdsContainerRef.current) {
        await document.exitFullscreen();
      }
      return;
    }

    setIsTvMode(true);
    await kdsContainerRef.current.requestFullscreen();
  };

  return (
    <div
      ref={kdsContainerRef}
      className={cn(
        "space-y-6 rounded-xl transition-colors duration-200",
        isTvMode && "tv-mode min-h-screen rounded-none p-6"
      )}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Select value={area} onChange={(event) => setArea(event.target.value)}>
          {areas.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
        <Button variant="outline" onClick={toggleTvMode}>
          {isTvMode ? (
            <>
              <Minimize2 className="mr-2 h-4 w-4" />
              Sair do modo TV
            </>
          ) : (
            <>
              <Maximize2 className="mr-2 h-4 w-4" />
              Modo TV
            </>
          )}
        </Button>
        {isTvMode && (
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
            isTvMode && "p-8 text-base"
          )}
        >
          Nenhum pedido pendente para a área <strong>{area}</strong> no momento.
        </div>
      )}

      <div className={cn("grid gap-4 xl:grid-cols-3", isTvMode && "gap-6")}>
        {KDS_COLUMNS.map((column) => (
          <section
            key={column.key}
            className={cn(
              "flex min-h-[65vh] flex-col rounded-xl border p-3",
              column.tone,
              isTvMode && "min-h-[78vh] p-4"
            )}
          >
            <header className="mb-3 rounded-lg bg-white/70 p-3 backdrop-blur-sm">
              <div className="flex items-center justify-between">
                <h2 className={cn("text-sm font-black tracking-wide", isTvMode && "text-lg")}>
                  {column.title}
                </h2>
                <span className="rounded-full bg-white px-3 py-1 text-sm font-bold text-slate-700">
                  {ordersByColumn[column.key].length}
                </span>
              </div>
              <p className="text-xs text-slate-600">
                {column.description}
              </p>
            </header>

            <div className="flex-1 space-y-3 overflow-y-auto pr-1">
              {ordersByColumn[column.key].length === 0 && (
                <p
                  className={cn(
                    "rounded-lg border border-dashed border-slate-300 bg-white/70 p-4 text-xs text-slate-500",
                    isTvMode && "text-sm"
                  )}
                >
                  Sem pedidos nessa etapa.
                </p>
              )}

              {ordersByColumn[column.key].map((order) => {
                const urgency = getUrgency(order.created_at);

                return (
                  <Card
                    key={order.id}
                    className={cn(
                      "border-2 border-slate-200 bg-white",
                      urgency.pulse && "animate-pulse border-red-500"
                    )}
                  >
                    <CardHeader className="space-y-3 pb-3">
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className={cn("text-3xl font-black", isTvMode && "text-4xl")}>
                          #{order.id}
                        </CardTitle>
                        <div
                          className={cn(
                            "rounded-full px-3 py-1 text-xs font-bold uppercase",
                            urgency.tone
                          )}
                        >
                          {urgency.elapsedMin} min
                        </div>
                      </div>
                      <div className="grid gap-1 text-sm">
                        <p className="font-semibold text-slate-700">
                          {order.cliente_nome}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="secondary">{formatOrderType(order.tipo_entrega)}</Badge>
                          <Badge variant="outline">
                            Pagamento: {order.forma_pagamento || "NÃO INFORMADO"}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <ul className="space-y-2 text-sm">
                        {(order.items ?? []).length === 0 && (
                          <li
                            className={cn(
                              "rounded-md border border-dashed border-slate-200 p-2 text-xs text-slate-500",
                              isTvMode && "text-sm"
                            )}
                          >
                            Pedido sem itens para exibir.
                          </li>
                        )}
                        {(order.items ?? []).map((item, index) => (
                          <li
                            key={`${item.id}-${item.name}-${index}`}
                            className="rounded-md bg-slate-100 p-3"
                          >
                            <p className="font-semibold tracking-wide text-slate-900">
                              {item.quantity}x {item.name.toUpperCase()}
                            </p>
                            {(item.modifiers ?? []).map((modifier, modifierIndex) => (
                              <p
                                key={`${modifier.name}-${modifierIndex}`}
                                className="pl-4 text-xs font-medium uppercase text-slate-500"
                              >
                                ↳ {modifier.name}
                              </p>
                            ))}
                          </li>
                        ))}
                      </ul>

                      {order.observacao ? (
                        <div className="rounded-lg border border-amber-300 bg-amber-100 p-3 text-xs font-semibold text-amber-900">
                          Observação: {order.observacao}
                        </div>
                      ) : null}

                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <Button
                          size="lg"
                          variant="outline"
                          onClick={() => startMutation.mutate(order.id)}
                          disabled={column.key !== "pending"}
                        >
                          Iniciar
                        </Button>
                        <Button
                          size="lg"
                          onClick={() => readyMutation.mutate(order.id)}
                          disabled={column.key === "ready"}
                        >
                          Marcar pronto
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
