"use client";

import Link from "next/link";
import { MobilePerformanceChart } from "@/components/mobile-performance-chart";
import { ArrowUpRight, CircleCheck, CircleHelp, Clock3, Flame, PackageCheck, ShoppingBag, Truck, UtensilsCrossed, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from "recharts";
import { type NameType, type ValueType } from "recharts/types/component/DefaultTooltipContent";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { DashboardDateFilter, DashboardPresetOption } from "@/components/dashboard-date-filter";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { AccessDenied } from "@/components/access-denied";
import { RequestErrorState, classifyRequestError } from "@/components/request-error-state";
import { useSession } from "@/hooks/use-session";
import { canAccessDashboard, permittedLandingPath } from "@/lib/authorization";

const recentOrderStatuses = {
  pending: { label: "Recebido", icon: Clock3, className: "border-slate-200 bg-slate-50 text-slate-600" },
  preparing: { label: "Em preparo", icon: Flame, className: "border-rose-200 bg-rose-50 text-rose-700" },
  ready: { label: "Pronto", icon: PackageCheck, className: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  delivering: { label: "Em entrega", icon: Truck, className: "border-sky-200 bg-sky-50 text-sky-700" },
  delivered: { label: "Entregue", icon: CircleCheck, className: "border-slate-200 bg-slate-100 text-slate-600" },
  canceled: { label: "Cancelado", icon: XCircle, className: "border-red-200 bg-red-50 text-red-700" },
};

const recentOrderStatusAliases: Record<string, keyof typeof recentOrderStatuses> = {
  RECEBIDO: "pending", PENDING: "pending", CONFIRMADO: "pending",
  EM_PREPARO: "preparing", PREPARANDO: "preparing", PREPARO: "preparing", PREPARING: "preparing",
  PRONTO: "ready", READY: "ready",
  SAIU: "delivering", OUT_FOR_DELIVERY: "delivering", SAIU_PARA_ENTREGA: "delivering", EM_ENTREGA: "delivering", DELIVERING: "delivering",
  ENTREGUE: "delivered", DELIVERED: "delivered",
  CANCELADO: "canceled", CANCELED: "canceled", CANCELLED: "canceled",
};

function RecentOrderStatus({ status }: { status: string }) {
  const key = recentOrderStatusAliases[String(status ?? "").trim().toUpperCase().replace(/\s+/g, "_")];
  const presentation = key ? recentOrderStatuses[key] : {
    label: "Não identificado", icon: CircleHelp, className: "border-slate-200 bg-slate-50 text-slate-500",
  };
  const Icon = presentation.icon;
  return (
    <span title={key ? undefined : status} className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-4 ${presentation.className}`}>
      <Icon className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
      {presentation.label}
    </span>
  );
}

interface OverviewResponse {
  total_orders?: number;
  total_revenue?: number;
  average_ticket?: number;
  active_customers?: number;
  orders_count?: number;
  gross_sales_cents?: number;
  avg_ticket_cents?: number;
}

interface TimeseriesPoint {
  bucket: string;
  revenue: number;
  orders: number;
}

interface TimeseriesApiPoint {
  date: string;
  gross_sales_cents: number;
  orders_count: number;
}

interface TopItem {
  name: string;
  quantity: number;
  revenue: number;
}

interface TopItemApi {
  name: string;
  qty: number;
  total_cents: number;
}

interface RecentOrder {
  id: number;
  daily_order_number?: number | null;
  status: string;
  total: number;
  created_at: string;
}

interface RecentOrderApi {
  id: number;
  daily_order_number?: number | null;
  status: string;
  total_cents: number;
  created_at: string | null;
}

const toNumber = (value: unknown) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const centsToCurrency = (value: unknown) => toNumber(value) / 100;

const money = (value: unknown) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(toNumber(value));

const toIsoDate = (date: Date) => {
  const tzOffsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - tzOffsetMs).toISOString().slice(0, 10);
};

const shiftDays = (baseDate: Date, days: number) => {
  const shifted = new Date(baseDate);
  shifted.setDate(shifted.getDate() + days);
  return shifted;
};

const DAY_IN_MS = 24 * 60 * 60 * 1000;
const CHART_STROKE_COLOR = "#dc2626";
const CHART_FILL_COLOR = "rgba(220,38,38,0.12)";
const CHART_ACTIVE_DOT_COLOR = "#ffffff";

const parseDateOnly = (value: string) => {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return Number.NaN;
  }
  return Date.UTC(year, month - 1, day);
};

const differenceInDays = (endDate: string, startDate: string) => {
  const end = parseDateOnly(endDate);
  const start = parseDateOnly(startDate);
  if (!Number.isFinite(end) || !Number.isFinite(start)) {
    return 0;
  }
  return Math.floor((end - start) / DAY_IN_MS);
};

function resolvePresetRange(preset: DashboardPresetOption) {
  const now = new Date();
  const today = toIsoDate(now);

  if (preset === "today") {
    return { start: today, end: today };
  }

  if (preset === "yesterday") {
    const yesterday = toIsoDate(shiftDays(now, -1));
    return { start: yesterday, end: yesterday };
  }

  if (preset === "last30") {
    return { start: toIsoDate(shiftDays(now, -29)), end: today };
  }

  return { start: toIsoDate(shiftDays(now, -6)), end: today };
}

export default function DashboardPage() {
  const { data: session, isLoading: isSessionLoading } = useSession();
  const [selectedPreset, setSelectedPreset] = useState<DashboardPresetOption>("last7");
  const [dateRange, setDateRange] = useState(() => resolvePresetRange("last7"));

  const normalizedRange = useMemo(() => {
    if (!dateRange.start || !dateRange.end) {
      return resolvePresetRange("last7");
    }

    if (dateRange.start <= dateRange.end) {
      return dateRange;
    }

    return {
      start: dateRange.end,
      end: dateRange.start,
    };
  }, [dateRange]);

  const selectedPeriodDays = useMemo(
    () => differenceInDays(normalizedRange.end, normalizedRange.start),
    [normalizedRange.end, normalizedRange.start]
  );

  const hasDashboardAccess = Boolean(session && canAccessDashboard(session.role));
  const { data, error, isLoading, isError } = useQuery({
    queryKey: ["dashboard", normalizedRange.start, normalizedRange.end],
    queryFn: async () => {
      const query = new URLSearchParams({
        start_date: normalizedRange.start,
        end_date: normalizedRange.end,
      }).toString();

      const [
        overviewResult,
        timeseriesResult,
        topItemsResult,
        recentOrdersResult,
      ] = await Promise.allSettled([
        api.get<OverviewResponse>(`/api/dashboard/overview?${query}`),
        api.get<{ points: TimeseriesApiPoint[] } | TimeseriesPoint[]>(
          `/api/dashboard/timeseries?${query}&bucket=day`
        ),
        api.get<{ items: TopItemApi[] } | TopItem[]>(`/api/dashboard/top-items?${query}&limit=8`),
        api.get<{ orders: RecentOrderApi[] } | RecentOrder[]>(`/api/dashboard/recent-orders?${query}&limit=8`),
      ]);

      if (overviewResult.status === "rejected") {
        throw overviewResult.reason;
      }

      const overviewResponse = overviewResult.value;
      const timeseriesResponse =
        timeseriesResult.status === "fulfilled" ? timeseriesResult.value : [];
      const topItemsResponse =
        topItemsResult.status === "fulfilled" ? topItemsResult.value : [];
      const recentOrdersResponse =
        recentOrdersResult.status === "fulfilled" ? recentOrdersResult.value : [];

      const overview: OverviewResponse = overviewResponse ?? {};
      const totalOrders = overview.total_orders ?? overview.orders_count ?? 0;
      const totalRevenue = overview.total_revenue ?? centsToCurrency(overview.gross_sales_cents);
      const averageTicket = overview.average_ticket ?? centsToCurrency(overview.avg_ticket_cents);

      const timeseriesData = Array.isArray(timeseriesResponse)
        ? timeseriesResponse
        : timeseriesResponse.points ?? [];
      const timeseries: TimeseriesPoint[] = timeseriesData.map((point) => {
        if ("bucket" in point) {
          return point as TimeseriesPoint;
        }
        const apiPoint = point as TimeseriesApiPoint;
        return {
          bucket: apiPoint.date,
          revenue: centsToCurrency(apiPoint.gross_sales_cents),
          orders: apiPoint.orders_count,
        };
      });

      const topItemsData = Array.isArray(topItemsResponse)
        ? topItemsResponse
        : topItemsResponse.items ?? [];
      const topItems: TopItem[] = topItemsData.map((item) => {
        if ("quantity" in item) {
          return item as TopItem;
        }
        const apiItem = item as TopItemApi;
        return {
          name: apiItem.name,
          quantity: apiItem.qty,
          revenue: centsToCurrency(apiItem.total_cents),
        };
      });

      const recentOrdersData = Array.isArray(recentOrdersResponse)
        ? recentOrdersResponse
        : recentOrdersResponse.orders ?? [];
      const recentOrders: RecentOrder[] = recentOrdersData.map((order) => {
        if ("total" in order) {
          return order as RecentOrder;
        }
        const apiOrder = order as RecentOrderApi;
        return {
          id: apiOrder.id,
          daily_order_number: apiOrder.daily_order_number,
          status: apiOrder.status,
          total: centsToCurrency(apiOrder.total_cents),
          created_at: apiOrder.created_at ?? "",
        };
      });

      return {
        overview: {
          total_orders: totalOrders,
          total_revenue: totalRevenue,
          average_ticket: averageTicket,
          active_customers: overview.active_customers,
        },
        timeseries,
        timeseriesAvailable: timeseriesResult.status === "fulfilled",
        topItems,
        recentOrders,
      };
    },
    enabled: hasDashboardAccess,
    retry: false,
  });

  const handlePresetChange = (value: DashboardPresetOption) => {
    setSelectedPreset(value);
    if (value !== "custom") {
      setDateRange(resolvePresetRange(value));
    }
  };

  const handleCustomStart = (value: string) => {
    setSelectedPreset("custom");
    setDateRange((current) => ({ ...current, start: value }));
  };

  const handleCustomEnd = (value: string) => {
    setSelectedPreset("custom");
    setDateRange((current) => ({ ...current, end: value }));
  };

  if (isSessionLoading) {
    return <LoadingExperience label="Preparando seu painel" compact />;
  }

  if (session && !hasDashboardAccess) {
    return <AccessDenied backHref={permittedLandingPath(session)} />;
  }

  if (isLoading) {
    return <LoadingExperience label="Organizando seus indicadores" />;
  }

  if (isError) {
    if (classifyRequestError(error) === "forbidden" && session) {
      return <AccessDenied backHref={permittedLandingPath(session)} />;
    }
    return <RequestErrorState error={error} />;
  }

  if (!data) {
    return <RequestErrorState error={new Error("Dashboard sem dados")} />;
  }

  const baseChartData =
    data.timeseries.length > 0
      ? [...data.timeseries]
      : [
          {
            bucket: normalizedRange.end,
            revenue: toNumber(data.overview.total_revenue),
            orders: toNumber(data.overview.total_orders),
          },
        ];

  const chartData = baseChartData
    .sort((a, b) => parseDateOnly(a.bucket) - parseDateOnly(b.bucket))
    .map((point, index) => ({
      ...point,
      xPosition: baseChartData.length === 1 ? 1 : index,
    }));

  const isSinglePoint = chartData.length === 1;

  const formatBucketLabel = (bucket: string) => {
    const bucketDate = new Date(`${bucket}T00:00:00`);
    if (Number.isNaN(bucketDate.getTime())) {
      return bucket;
    }

    if (selectedPeriodDays <= 1) {
      return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).format(
        bucketDate
      );
    }

    if (selectedPeriodDays <= 7) {
      return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).format(
        bucketDate
      );
    }

    return new Intl.DateTimeFormat("en-US", { month: "short", day: "2-digit" }).format(bucketDate);
  };

  const renderTooltipContent = ({ active, payload }: TooltipProps<ValueType, NameType>) => {
    if (!active || !payload || payload.length === 0) {
      return null;
    }

    const point = payload[0]?.payload as TimeseriesPoint | undefined;
    if (!point) {
      return null;
    }

    return (
      <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-md">
        <p className="font-medium text-slate-900">{formatBucketLabel(point.bucket)}</p>
        <p className="text-slate-700">Receita: R$ {money(point.revenue)}</p>
        <p className="text-slate-700">Pedidos: {toNumber(point.orders)}</p>
      </div>
    );
  };

  return (
    <div className="space-y-6 lg:space-y-8">
      <section className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm lg:hidden">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700" aria-hidden="true">
          <ShoppingBag className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-[13px] font-semibold leading-5 text-slate-900">Sua operação</h1>
          <p className="hidden text-[11px] leading-4 text-slate-500 min-[360px]:block">Pedidos e cozinha em um toque</p>
        </div>
        <Link href="/orders" className="inline-flex min-h-10 shrink-0 items-center gap-1 rounded-xl px-2 text-xs font-semibold text-brand-700 transition-colors hover:bg-brand-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">Ver pedidos <ArrowUpRight className="h-4 w-4" /></Link>
      </section>
      <nav aria-label="Atalhos da operação" className="grid grid-cols-3 gap-2 lg:hidden">
        {[{ label: "Pedidos", href: "/orders", icon: ShoppingBag }, { label: "Cozinha", href: "/kds", icon: Flame }, { label: "Cardápio", href: "/menu", icon: UtensilsCrossed }].map(item => <Link key={item.href} href={item.href} className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border border-slate-200/80 bg-white text-xs font-semibold text-slate-700"><span className="rounded-xl bg-brand-50 p-2 text-brand-600"><item.icon className="h-5 w-5" /></span>{item.label}</Link>)}
      </nav>
      <section className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-900"><span className="lg:hidden">Visão geral</span><span className="hidden lg:inline">Dashboard</span></h2>
          <p className="text-sm text-slate-500">Acompanhe os principais indicadores por período.</p>
        </div>
        <DashboardDateFilter
          preset={selectedPreset}
          start={dateRange.start}
          end={dateRange.end}
          onPresetChange={handlePresetChange}
          onStartChange={handleCustomStart}
          onEndChange={handleCustomEnd}
        />
      </section>

      <section className="admin-dashboard-stats grid grid-cols-2 gap-3 xl:grid-cols-4 lg:gap-6">
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Pedidos</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {toNumber(data.overview.total_orders)}
          </CardContent>
        </Card>
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Faturamento</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            R$ {money(data.overview.total_revenue)}
          </CardContent>
        </Card>
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Ticket médio</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            R$ {money(data.overview.average_ticket)}
          </CardContent>
        </Card>
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Clientes ativos</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {data.overview.active_customers ?? "-"}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <Card className="min-w-0 h-full xl:col-span-2">
          <div className="lg:hidden"><MobilePerformanceChart key={`${normalizedRange.start}:${normalizedRange.end}`} points={data.timeseries} start={normalizedRange.start} end={normalizedRange.end} available={data.timeseriesAvailable} /></div>
          <div className="hidden lg:block">
          <CardHeader>
            <CardTitle>Performance diária</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                <XAxis
                  type={isSinglePoint ? "number" : "category"}
                  dataKey={isSinglePoint ? "xPosition" : "bucket"}
                  domain={isSinglePoint ? [0, 2] : undefined}
                  ticks={isSinglePoint ? [1] : undefined}
                  tickFormatter={(value) => {
                    if (isSinglePoint) {
                      return formatBucketLabel(chartData[0]?.bucket ?? "");
                    }
                    return formatBucketLabel(String(value));
                  }}
                  stroke="#94a3b8"
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} />
                <Tooltip content={renderTooltipContent} />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  fill={CHART_FILL_COLOR}
                  stroke="none"
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke={CHART_STROKE_COLOR}
                  strokeWidth={2}
                  dot={{ r: 4, fill: CHART_STROKE_COLOR, stroke: "#ffffff", strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: CHART_ACTIVE_DOT_COLOR, stroke: CHART_STROKE_COLOR, strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
          </div>
        </Card>
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Top itens</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 lg:hidden">
              {data.topItems.length === 0 && <p className="text-sm text-slate-500">Nenhum item vendido neste período.</p>}
              {data.topItems.map((item, index) => <div key={item.name} className="flex items-center gap-3 rounded-xl bg-slate-50 p-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-xs font-bold text-slate-500">{index + 1}</span><div className="min-w-0 flex-1"><p className="break-words text-sm font-semibold">{item.name}</p><p className="mt-1 text-xs text-slate-500">{toNumber(item.quantity)} vendidos</p></div><p className="shrink-0 text-sm font-semibold">R$ {money(item.revenue)}</p></div>)}
            </div>
            <div className="hidden lg:block"><Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead>Qtd</TableHead>
                  <TableHead>Receita</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.topItems.map((item) => (
                  <TableRow key={item.name}>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>{toNumber(item.quantity)}</TableCell>
                    <TableCell>R$ {money(item.revenue)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table></div>
          </CardContent>
        </Card>
      </section>

      <section>
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Pedidos recentes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-slate-100 lg:hidden">
              {data.recentOrders.length === 0 && <p className="text-sm text-slate-500">Seus pedidos aparecerão aqui.</p>}
              {data.recentOrders.map(order => <Link key={order.id} href="/orders" className="flex min-h-20 items-center justify-between gap-3 py-3"><div className="min-w-0"><p className="text-sm font-semibold">Pedido #{order.daily_order_number ?? order.id}</p><div className="mt-2"><RecentOrderStatus status={order.status} /></div></div><div className="flex shrink-0 items-center gap-2"><span className="text-sm font-semibold">R$ {money(order.total)}</span><ArrowUpRight className="h-4 w-4 text-slate-400" /></div></Link>)}
            </div>
            <div className="hidden lg:block"><Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Criado em</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recentOrders.map((order) => (
                  <TableRow key={order.id}>
                    <TableCell>#{order.daily_order_number ?? order.id}</TableCell>
                    <TableCell><RecentOrderStatus status={order.status} /></TableCell>
                    <TableCell>R$ {money(order.total)}</TableCell>
                    <TableCell>
                      {order.created_at
                        ? new Date(order.created_at).toLocaleString("pt-BR")
                        : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table></div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
