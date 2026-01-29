"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, baseUrl } from "@/lib/api";

interface FinancialSummary {
  gross_revenue_cents: number;
  net_revenue_cents: number;
  orders_count: number;
  average_ticket_cents: number;
  fees_cents: number;
  cogs_cents?: number;
}

interface TopItem {
  name: string;
  quantity: number;
  revenue_cents: number;
}

interface LowStockItem {
  inventory_item_id: number;
  name: string;
  current_stock: number;
  min_stock_level: number;
}

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

export default function ReportsPage({ params }: { params: { tenantId: string } }) {
  const tenantId = params.tenantId;
  const [fromDate, setFromDate] = useState(formatDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)));
  const [toDate, setToDate] = useState(formatDate(new Date()));

  const { data, isLoading, isError } = useQuery({
    queryKey: ["reports", tenantId, fromDate, toDate],
    queryFn: async () => {
      const query = `tenant_id=${tenantId}&from=${fromDate}&to=${toDate}`;
      const [summary, topItems, lowStock] = await Promise.all([
        api.get<FinancialSummary>(`/api/reports/financial/summary?${query}`),
        api.get<TopItem[]>(`/api/reports/sales/top-items?${query}`),
        api.get<LowStockItem[]>(`/api/reports/inventory/low-stock?${query}`),
      ]);
      return { summary, topItems, lowStock };
    },
  });

  const exportFinancialUrl = `${baseUrl}/api/reports/export/financial.csv?tenant_id=${tenantId}&from=${fromDate}&to=${toDate}`;
  const exportTopItemsUrl = `${baseUrl}/api/reports/export/top-items.csv?tenant_id=${tenantId}&from=${fromDate}&to=${toDate}`;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Relatórios financeiros</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div>
              <label className="text-xs text-slate-500">De</label>
              <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-slate-500">Até</label>
              <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
            </div>
            <div className="flex items-end gap-2">
              <Button asChild variant="outline">
                <a href={exportFinancialUrl} target="_blank" rel="noreferrer">
                  Export CSV Financeiro
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href={exportTopItemsUrl} target="_blank" rel="noreferrer">
                  Export Top Itens
                </a>
              </Button>
            </div>
          </div>
          {isLoading && <p className="text-sm text-slate-500">Carregando...</p>}
          {isError && (
            <p className="text-sm text-red-600">Erro ao carregar relatórios.</p>
          )}
          {data && (
            <div className="grid gap-4 md:grid-cols-4">
              <div>
                <p className="text-sm text-slate-500">Pedidos</p>
                <p className="text-xl font-semibold">{data.summary.orders_count}</p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Receita bruta</p>
                <p className="text-xl font-semibold">
                  R$ {(data.summary.gross_revenue_cents / 100).toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Receita líquida</p>
                <p className="text-xl font-semibold">
                  R$ {(data.summary.net_revenue_cents / 100).toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Ticket médio</p>
                <p className="text-xl font-semibold">
                  R$ {(data.summary.average_ticket_cents / 100).toFixed(2)}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <section className="grid gap-4 xl:grid-cols-2">
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
                {data?.topItems.map((item) => (
                  <TableRow key={item.name}>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>{item.quantity}</TableCell>
                    <TableCell>R$ {(item.revenue_cents / 100).toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Baixo estoque</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead>Atual</TableHead>
                  <TableHead>Mínimo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.lowStock.map((item) => (
                  <TableRow key={item.inventory_item_id}>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>{item.current_stock}</TableCell>
                    <TableCell>{item.min_stock_level}</TableCell>
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
