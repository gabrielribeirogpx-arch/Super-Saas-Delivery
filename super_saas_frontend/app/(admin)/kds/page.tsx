"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Maximize2, Minimize2 } from "lucide-react";

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
  total: number;
  cliente_nome?: string;
  cliente_telefone?: string;
  tipo_entrega?: string;
  order_type?: string;
  observacao?: string;
  forma_pagamento?: string;
  troco_para?: number;
  canal?: string;
  street?: string;
  number?: string;
  neighborhood?: string;
  city?: string;
  reference?: string;
  mesa?: string;
  comanda?: string;
  ready_areas?: string[];
  items: KdsItem[];
}

interface KdsOrderApi {
  id?: number;
  status?: string;
  created_at?: string;
  cliente_nome?: unknown;
  cliente_telefone?: unknown;
  customer_phone?: unknown;
  tipo_entrega?: unknown;
  order_type?: unknown;
  observacao?: unknown;
  order_note?: unknown;
  forma_pagamento?: unknown;
  payment_method?: unknown;
  payment_change_for?: unknown;
  troco_para?: unknown;
  canal?: unknown;
  channel?: unknown;
  origem?: unknown;
  source?: unknown;
  endereco?: unknown;
  delivery_address?: unknown;
  delivery_address_json?: unknown;
  endereco_entrega?: unknown;
  street?: unknown;
  number?: unknown;
  neighborhood?: unknown;
  bairro?: unknown;
  city?: unknown;
  reference?: unknown;
  referencia?: unknown;
  table_number?: unknown;
  mesa?: unknown;
  table?: unknown;
  command_number?: unknown;
  comanda?: unknown;
  total?: unknown;
  total_amount?: unknown;
  valor_total?: unknown;
  ready_areas?: unknown;
  items?: unknown;
  itens?: unknown;
}

interface KdsModifierApi {
  name?: unknown;
  nome?: unknown;
  label?: unknown;
  option_name?: unknown;
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

const toSafeString = (value: unknown) => (typeof value === "string" ? value.trim() : "");

const toSafeNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value.replace(/\./g, "").replace(",", ".").trim();
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
};

const toSafeAddress = (value: unknown) => {
  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as {
    street?: unknown;
    number?: unknown;
    district?: unknown;
    neighborhood?: unknown;
    bairro?: unknown;
    city?: unknown;
    reference?: unknown;
    referencia?: unknown;
  };

  return {
    street: toSafeString(record.street),
    number: toSafeString(record.number),
    neighborhood:
      toSafeString(record.district) ||
      toSafeString(record.neighborhood) ||
      toSafeString(record.bairro),
    city: toSafeString(record.city),
    reference: toSafeString(record.reference) || toSafeString(record.referencia),
  };
};

const toSafeModifiers = (value: unknown): Array<{ name: string }> => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((modifier) => {
      if (!modifier || typeof modifier !== "object") {
        return null;
      }

      const rawModifier = modifier as KdsModifierApi;
      const rawName =
        rawModifier.name ?? rawModifier.nome ?? rawModifier.label ?? rawModifier.option_name;
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

    const modifiers = toSafeModifiers(itemData.modifiers);

    items.push({
      id: Number(itemData.id) || 0,
      name: typeof itemData.name === "string" ? itemData.name : "Item sem nome",
      quantity: Number(itemData.quantity) || 0,
      production_area:
        typeof itemData.production_area === "string" ? itemData.production_area : undefined,
      modifiers,
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
      const totalCandidates = [order.total, order.total_amount, order.valor_total];
      const parsedTotal = totalCandidates
        .map((candidate) => {
          if (typeof candidate === "number") {
            return Number.isFinite(candidate) ? candidate : 0;
          }

          if (typeof candidate === "string") {
            const normalized = candidate.replace(/\./g, "").replace(",", ".").trim();
            const asNumber = Number(normalized);
            return Number.isFinite(asNumber) ? asNumber : 0;
          }

          return 0;
        })
        .find((value) => value > 0) ?? 0;

      const address =
        toSafeAddress({
          street: order.street,
          number: order.number,
          neighborhood: order.neighborhood ?? order.bairro,
          city: order.city,
          reference: order.reference ?? order.referencia,
        }) ??
        toSafeAddress(order.endereco) ??
        toSafeAddress(order.delivery_address) ??
        toSafeAddress(order.delivery_address_json) ??
        toSafeAddress(order.endereco_entrega);

      const mesaFromFields =
        toSafeString(order.table_number) || toSafeString(order.mesa) || toSafeString(order.table);
      const mesaFromTypeMatch = toSafeString(order.tipo_entrega).match(/MESA\s*#?\s*([A-Z0-9-]+)/i);
      const mesa = mesaFromFields || (mesaFromTypeMatch ? mesaFromTypeMatch[1] : "");
      const comanda = toSafeString(order.command_number) || toSafeString(order.comanda);

      return {
        id: Number(order.id) || 0,
        status: typeof order.status === "string" ? order.status : "PENDING",
        created_at: typeof order.created_at === "string" ? order.created_at : "",
        total: parsedTotal,
        cliente_nome:
          typeof order.cliente_nome === "string" && order.cliente_nome.trim()
            ? order.cliente_nome
            : "Cliente não informado",
        cliente_telefone:
          typeof order.cliente_telefone === "string" && order.cliente_telefone.trim()
            ? order.cliente_telefone
            : typeof order.customer_phone === "string" && order.customer_phone.trim()
              ? order.customer_phone
              : "",
        tipo_entrega: typeof order.tipo_entrega === "string" ? order.tipo_entrega : "",
        order_type: typeof order.order_type === "string" ? order.order_type : "",
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
        troco_para: toSafeNumber(order.payment_change_for) ?? toSafeNumber(order.troco_para) ?? undefined,
        canal:
          typeof order.canal === "string"
            ? order.canal
            : typeof order.channel === "string"
              ? order.channel
              : typeof order.origem === "string"
                ? order.origem
                : typeof order.source === "string"
                  ? order.source
                  : "",
        street: address?.street,
        number: address?.number,
        neighborhood: address?.neighborhood,
        city: address?.city,
        reference: address?.reference,
        mesa,
        comanda,
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
  const [toastQueue, setToastQueue] = useState<KdsOrder[]>([]);
  const [activeToast, setActiveToast] = useState<KdsOrder | null>(null);
  const [highlightedOrderId, setHighlightedOrderId] = useState<number | null>(null);
  const kdsContainerRef = useRef<HTMLDivElement>(null);
  const knownOrderIdsRef = useRef<Set<number>>(new Set());
  const orderCardRefs = useRef(new Map<number, HTMLDivElement>());
  const dismissTimeoutRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

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
    if (!data) return;

    if (knownOrderIdsRef.current.size === 0) {
      knownOrderIdsRef.current = new Set(data.map((order) => order.id));
      return;
    }

    const knownIds = knownOrderIdsRef.current;
    const incoming = data.filter((order) => !knownIds.has(order.id));

    if (incoming.length > 0) {
      setToastQueue((currentQueue) => [...currentQueue, ...incoming]);
      incoming.forEach((order) => {
        knownIds.add(order.id);
      });
    }
  }, [data]);

  useEffect(() => {
    if (activeToast || toastQueue.length === 0) return;

    setActiveToast(toastQueue[0]);
    setToastQueue((currentQueue) => currentQueue.slice(1));
  }, [toastQueue, activeToast]);

  useEffect(() => {
    if (!activeToast) return;

    dismissTimeoutRef.current = window.setTimeout(() => {
      setActiveToast(null);
    }, 7000);

    const playNotificationSound = () => {
      const AudioCtx = window.AudioContext || (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;

      const ctx = audioContextRef.current ?? new AudioCtx();
      audioContextRef.current = ctx;

      if (ctx.state === "suspended") {
        void ctx.resume();
      }

      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(880, ctx.currentTime);
      oscillator.frequency.setValueAtTime(1175, ctx.currentTime + 0.12);
      gainNode.gain.setValueAtTime(0.0001, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.1, ctx.currentTime + 0.02);
      gainNode.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.36);
      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);
      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + 0.4);
    };

    playNotificationSound();

    return () => {
      if (dismissTimeoutRef.current) {
        window.clearTimeout(dismissTimeoutRef.current);
      }
    };
  }, [activeToast]);

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

  const formatOrderType = (type?: string, orderType?: string) => {
    const normalizedOrderType = (orderType || "").trim().toLowerCase();
    if (normalizedOrderType === "delivery") return "ENTREGA";
    if (normalizedOrderType === "pickup") return "RETIRADA";
    if (normalizedOrderType === "table") return "MESA";

    const normalized = (type || "").trim().toUpperCase();
    if (normalized.includes("ENTREGA")) return "ENTREGA";
    if (normalized.includes("RETIRADA")) return "RETIRADA";
    if (normalized.includes("MESA")) return "MESA";
    return "";
  };

  const formatOrderTypeLabel = (type?: string, orderType?: string, mesa?: string) => {
    const normalized = formatOrderType(type, orderType);
    if (normalized === "ENTREGA") return "ENTREGA";
    if (normalized === "RETIRADA") return "RETIRADA NO BALCÃO";
    if (normalized === "MESA" && mesa) return `MESA ${mesa}`;
    if (normalized === "MESA") return "MESA";
    return "";
  };

  const formatChannel = (channel?: string) => {
    if (!channel || !channel.trim()) {
      return "";
    }

    return channel.trim();
  };

  const formatCreatedAt = (createdAt?: string) => {
    if (!createdAt) {
      return "";
    }

    const createdDate = new Date(createdAt);
    if (Number.isNaN(createdDate.getTime())) {
      return "";
    }

    return createdDate.toLocaleString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "2-digit",
    });
  };

  const formatMoney = (value: number) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      minimumFractionDigits: 2,
    }).format(value || 0);

  const formatDeliveryAddressLines = (order: KdsOrder) => {
    const streetLine = [order.street, order.number].filter(Boolean).join(", ");
    const neighborhoodCityLine = [order.neighborhood, order.city].filter(Boolean).join(" - ");
    const referenceLine = order.reference ? `Ref: ${order.reference}` : "";

    return [streetLine, neighborhoodCityLine, referenceLine].filter(Boolean);
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

  const goToOrder = (orderId: number) => {
    setHighlightedOrderId(orderId);
    const targetCard = orderCardRefs.current.get(orderId);
    if (targetCard) {
      targetCard.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    setActiveToast(null);
    window.setTimeout(() => setHighlightedOrderId(null), 2000);
  };

  return (
    <div
      ref={kdsContainerRef}
      className={cn(
        "space-y-6 rounded-xl bg-white transition-colors duration-200",
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
                const orderType = formatOrderType(order.tipo_entrega, order.order_type);
                const orderTypeLabel = formatOrderTypeLabel(order.tipo_entrega, order.order_type, order.mesa);
                const createdAtLabel = formatCreatedAt(order.created_at);
                const orderVisualStatus = urgency.elapsedMin >= 25 ? "overdue" : column.key;
                const statusBorderTone = {
                  pending: "border-l-slate-400",
                  preparing: "border-l-amber-400",
                  ready: "border-l-emerald-500",
                  overdue: "border-l-red-600",
                }[orderVisualStatus];

                return (
                  <Card
                    key={order.id}
                    ref={(element) => {
                      if (element) {
                        orderCardRefs.current.set(order.id, element);
                        return;
                      }

                      orderCardRefs.current.delete(order.id);
                    }}
                    className={cn(
                      "break-inside-avoid border-2 border-slate-200 border-l-8 bg-white transition-shadow duration-300 print:shadow-none",
                      statusBorderTone,
                      highlightedOrderId === order.id && "ring-2 ring-blue-400 shadow-xl",
                      urgency.pulse && "animate-pulse border-red-500"
                    )}
                  >
                    <CardHeader className="space-y-4 pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className={cn("text-4xl font-black leading-none", isTvMode && "text-5xl")}>
                          #{order.id}
                        </CardTitle>
                        <div
                          className={cn(
                            "rounded-full px-3 py-1 text-sm font-black uppercase",
                            urgency.tone
                          )}
                        >
                          {urgency.elapsedMin} min
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {orderTypeLabel && (
                          <Badge className="px-3 py-1 text-sm font-bold uppercase" variant="secondary">
                            {orderTypeLabel}
                          </Badge>
                        )}
                        {orderType === "MESA" && order.comanda && (
                          <Badge className="px-3 py-1 text-sm font-black uppercase" variant="warning">
                            COMANDA {order.comanda}
                          </Badge>
                        )}
                      </div>

                      <div className="grid gap-1.5 rounded-md bg-slate-50 p-3 text-sm">
                        <p className="text-base font-bold text-slate-800">{order.cliente_nome}</p>
                        {order.cliente_telefone && <p className="font-semibold text-slate-700">Telefone: {order.cliente_telefone}</p>}
                        {order.forma_pagamento && <p className="font-semibold text-slate-700">Pagamento: {order.forma_pagamento}</p>}
                        {order.troco_para !== undefined && <p className="font-semibold text-slate-700">Troco: {formatMoney(order.troco_para)}</p>}
                        {formatChannel(order.canal) && <p className="font-semibold text-slate-700">Canal: {formatChannel(order.canal)}</p>}
                        {createdAtLabel && <p className="font-semibold text-slate-700">Criado: {createdAtLabel}</p>}
                      </div>

                      {order.order_type?.trim().toLowerCase() === "delivery" &&
                        formatDeliveryAddressLines(order).length > 0 && (
                          <div className="rounded-md border border-slate-200 p-3 text-sm">
                            {formatDeliveryAddressLines(order).map((line, lineIndex) => (
                              <p key={`${order.id}-address-${lineIndex}`} className="font-semibold text-slate-700">
                                {line}
                              </p>
                            ))}
                          </div>
                        )}

                      {orderType === "RETIRADA" && (
                        <div className="rounded-md border border-slate-200 p-3 text-sm font-semibold text-slate-700">
                          RETIRADA NO BALCÃO
                        </div>
                      )}

                      {orderType === "MESA" && order.mesa && order.comanda && (
                        <div className="rounded-md border border-slate-200 p-3 text-xl font-black tracking-wide text-slate-900">
                          MESA {order.mesa} - COMANDA {order.comanda}
                        </div>
                      )}
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <ul className="space-y-3 text-base">
                        {(order.items ?? []).length === 0 && (
                          <li
                            className={cn(
                              "rounded-md border border-dashed border-slate-200 p-3 text-sm text-slate-500",
                              isTvMode && "text-sm"
                            )}
                          >
                            Pedido sem itens para exibir.
                          </li>
                        )}
                        {(order.items ?? []).map((item, index) => (
                          <li
                            key={`${item.id}-${item.name}-${index}`}
                            className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3"
                          >
                            <div className="flex items-start gap-3">
                              <span className="min-w-[2.4rem] rounded-md bg-white px-2 py-1 text-center text-lg font-black text-slate-900">
                                {item.quantity}x
                              </span>
                              <p className="pt-1 text-base font-bold uppercase tracking-wide text-slate-900">
                                {item.name}
                              </p>
                            </div>
                            {(item.modifiers ?? []).length > 0 && (
                              <div className="mt-1 space-y-1 pl-14">
                                {(item.modifiers ?? []).map((modifier, modifierIndex) => (
                                  <p
                                    key={`${modifier.name}-${modifierIndex}`}
                                    className="text-sm font-semibold text-slate-500"
                                  >
                                    {modifier.name}
                                  </p>
                                ))}
                              </div>
                            )}
                          </li>
                        ))}
                      </ul>

                      {order.observacao ? (
                        <div className="rounded-lg border-2 border-amber-400 bg-amber-100 p-3 text-sm font-bold text-amber-900">
                          <p className="mb-1 flex items-center gap-2 uppercase">
                            <AlertTriangle className="h-4 w-4" /> Observação
                          </p>
                          <p>{order.observacao}</p>
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

      <aside
        className={cn(
          "pointer-events-none fixed right-5 top-5 z-50 w-full max-w-sm transition-all duration-300",
          activeToast ? "translate-x-0 opacity-100" : "translate-x-8 opacity-0"
        )}
        aria-live="polite"
      >
        <div className="pointer-events-auto rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
          {activeToast ? (
            <>
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-900">Novo pedido recebido</p>
                <p className="text-lg font-black text-slate-900">#{activeToast.id}</p>
                <p className="text-sm text-slate-600">Tipo: {formatOrderTypeLabel(activeToast.tipo_entrega, activeToast.order_type, activeToast.mesa)}</p>
                <p className="text-sm text-slate-600">Total: {formatMoney(activeToast.total)}</p>
              </div>
              <div className="flex items-center justify-end gap-2">
                <Button size="sm" variant="outline" onClick={() => goToOrder(activeToast.id)}>
                  Ver Pedido
                </Button>
                <Button size="sm" onClick={() => setActiveToast(null)}>
                  OK
                </Button>
              </div>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
