"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardDateFilter, DashboardPresetOption } from "@/components/dashboard-date-filter";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

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

const money = (value: unknown) => toNumber(value).toFixed(2);

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

  const { data, isLoading, isError } = useQuery({
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
        topItems,
        recentOrders,
      };
    },
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

  if (isLoading) {
    return <p className="text-sm text-slate-500">Carregando dashboard...</p>;
  }

  if (isError || !data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar o dashboard. Verifique se o backend está rodando.
      </div>
    );
  }

  const chartMode = selectedPeriodDays <= 1 ? "kpi" : selectedPeriodDays <= 7 ? "line" : "bar";
  const sparklineData =
    data.recentOrders.length > 0
      ? [...data.recentOrders]
          .sort(
            (a, b) =>
              new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
          )
          .map((order, index) => ({
            bucket: String(index),
            revenue: toNumber(order.total),
          }))
      : [{ bucket: "0", revenue: toNumber(data.overview.total_revenue) }];

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Dashboard</h2>
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

      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
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
        <Card className="h-full xl:col-span-2">
          <CardHeader>
            <CardTitle>Performance diária</CardTitle>
          </CardHeader>
          {chartMode === "kpi" ? (
            <CardContent className="space-y-4">
              <p className="text-sm font-medium text-slate-600">Performance hoje</p>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Receita</p>
                  <p className="text-lg font-semibold text-slate-900">R$ {money(data.overview.total_revenue)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Pedidos</p>
                  <p className="text-lg font-semibold text-slate-900">{toNumber(data.overview.total_orders)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Ticket médio</p>
                  <p className="text-lg font-semibold text-slate-900">R$ {money(data.overview.average_ticket)}</p>
                </div>
              </div>
              <div className="h-16">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={sparklineData}>
                    <Tooltip formatter={(value: number | string) => `R$ ${money(value)}`} />
                    <Line
                      type="monotone"
                      dataKey="revenue"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          ) : (
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                {chartMode === "line" ? (
                  <LineChart data={data.timeseries}>
                    <XAxis dataKey="bucket" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="revenue"
                      stroke="#3b82f6"
                      strokeWidth={3}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                ) : (
                  <BarChart data={data.timeseries}>
                    <XAxis dataKey="bucket" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip />
                    <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                )}
              </ResponsiveContainer>
            </CardContent>
          )}
        </Card>
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Top itens</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
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
            </Table>
          </CardContent>
        </Card>
      </section>

      <section>
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Pedidos recentes</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
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
                    <TableCell>{order.status}</TableCell>
                    <TableCell>R$ {money(order.total)}</TableCell>
                    <TableCell>
                      {order.created_at
                        ? new Date(order.created_at).toLocaleString("pt-BR")
                        : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
