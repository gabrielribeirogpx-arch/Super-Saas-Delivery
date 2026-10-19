"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ManualPaymentsPanel } from "@/components/ManualPaymentsPanel";
import { useSession } from "@/hooks/use-session";
import { canManagePayments, formatBRL } from "@/lib/manualPayments";
import { api } from "@/lib/api";

interface CashSummary {
  opening_balance_cents: number;
  total_in_cents: number;
  total_out_cents: number;
  net_cents: number;
  by_category: Record<string, number>;
}

interface CashMovement {
  id: number;
  type: string;
  category: string;
  description?: string;
  amount_cents: number;
  occurred_at: string;
}

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

export default function FinancePage() {
  const { data: session } = useSession();
  const today = formatDate(new Date());
  const [fromDate, setFromDate] = useState(formatDate(new Date(Date.now() - 6 * 24 * 60 * 60 * 1000)));
  const [toDate, setToDate] = useState(today);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["finance", session?.tenant_id, fromDate, toDate],
    enabled: canManagePayments(session?.role),
    queryFn: async () => {
      const query = `from=${fromDate}&to=${toDate}`;
      const [summary, movements] = await Promise.all([
        api.get<CashSummary>(`/api/finance/cash/summary?${query}`),
        api.get<CashMovement[]>(`/api/finance/cash/movements?${query}`),
      ]);
      return { summary, movements };
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Financeiro</h1>
      <div className="flex flex-wrap gap-3">
            <div>
              <label htmlFor="finance-from" className="text-xs text-slate-500">De</label>
              <Input id="finance-from" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            </div>
            <div>
              <label htmlFor="finance-to" className="text-xs text-slate-500">Até</label>
              <Input id="finance-to" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
            </div>
          </div>

      <Card>
        <CardHeader>
          <CardTitle>Resumo do caixa</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div>
            <p className="text-sm text-slate-500">Entradas</p>
            <p className="text-xl font-semibold">
              {data ? formatBRL(data.summary.total_in_cents) : "—"}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Saídas</p>
            <p className="text-xl font-semibold">
              {data ? formatBRL(data.summary.total_out_cents) : "—"}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Saldo líquido</p>
            <p className="text-xl font-semibold">
              {data ? formatBRL(data.summary.net_cents) : "—"}
            </p>
          </div>
        </CardContent>
      </Card>

      <ManualPaymentsPanel fromDate={fromDate} toDate={toDate} />

      <Card>
        <CardHeader>
          <CardTitle>Movimentos</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">


          {isLoading && <p className="text-sm text-slate-500">Carregando...</p>}
          {isError && (
            <p className="text-sm text-red-600">Erro ao carregar movimentos.</p>
          )}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tipo</TableHead>
                <TableHead>Categoria</TableHead>
                <TableHead>Descrição</TableHead>
                <TableHead>Valor</TableHead>
                <TableHead>Data</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.movements?.map((movement) => (
                <TableRow key={movement.id}>
                  <TableCell>{movement.type}</TableCell>
                  <TableCell>{movement.category}</TableCell>
                  <TableCell>{movement.description ?? "-"}</TableCell>
                  <TableCell>
                    R$ {(movement.amount_cents / 100).toFixed(2)}
                  </TableCell>
                  <TableCell>
                    {new Date(movement.occurred_at).toLocaleString("pt-BR")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
