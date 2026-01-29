"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  status: string;
  total: number;
  created_at: string;
}

interface RecentOrderApi {
  id: number;
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

export default function DashboardPage({ params }: { params: { tenantId: string } }) {
  const router = useRouter();
  const tenantIdNum = Number(params.tenantId);
  const isTenantValid = Number.isFinite(tenantIdNum);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard", tenantIdNum],
    enabled: isTenantValid,
    queryFn: async () => {
      const query = `tenant_id=${tenantIdNum}`;
      const [overviewResponse, timeseriesResponse, topItemsResponse, recentOrdersResponse] = await Promise.all([
        api.get<OverviewResponse>(`/api/dashboard/overview?${query}`),
        api.get<{ points: TimeseriesApiPoint[] } | TimeseriesPoint[]>(
          `/api/dashboard/timeseries?${query}&bucket=day`
        ),
        api.get<{ items: TopItemApi[] } | TopItem[]>(`/api/dashboard/top-items?${query}&limit=8`),
        api.get<{ orders: RecentOrderApi[] } | RecentOrder[]>(`/api/dashboard/recent-orders?${query}&limit=8`),
      ]);

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

  useEffect(() => {
    if (!isTenantValid) {
      router.replace("/login");
    }
  }, [isTenantValid, router]);

  if (!isTenantValid) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
        Tenant inválido.
      </div>
    );
  }

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

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Pedidos</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {toNumber(data.overview.total_orders)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Faturamento</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            R$ {money(data.overview.total_revenue)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Ticket médio</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            R$ {money(data.overview.average_ticket)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Clientes ativos</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {data.overview.active_customers ?? "-"}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Performance diária</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.timeseries}>
                <XAxis dataKey="bucket" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
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
        <Card>
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
                    <TableCell>#{order.id}</TableCell>
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
