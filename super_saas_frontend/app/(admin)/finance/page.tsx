"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, CalendarRange, Landmark, ReceiptText, WalletCards } from "lucide-react";
import { AccessDenied } from "@/components/access-denied";
import { isForbiddenError } from "@/components/request-error-state";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingExperience } from "@/components/ui/loading-experience";
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

  const { data, isLoading, isError, error } = useQuery({
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

  if ((session && !canManagePayments(session.role)) || isForbiddenError(error)) return <AccessDenied />;

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 pb-10">
      <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-600"><Landmark className="h-4 w-4" aria-hidden="true" />Gestão financeira</div>
          <h1 className="text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">Financeiro</h1>
          <p className="mt-2 max-w-xl text-sm text-slate-500">Acompanhe o caixa, confira recebimentos e mantenha cada movimentação sob controle.</p>
        </div>
        <div className="rounded-2xl border border-slate-200/80 bg-white p-2 shadow-[0_14px_35px_-28px_rgba(15,23,42,0.65)]">
          <div className="mb-1.5 flex items-center gap-2 px-2 pt-1 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400"><CalendarRange className="h-3.5 w-3.5" aria-hidden="true" />Período analisado</div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="finance-from" className="sr-only">De</label>
              <Input id="finance-from" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="h-10 min-w-0 border-0 bg-slate-50 text-xs font-semibold shadow-none sm:min-w-36" />
            </div>
            <div>
              <label htmlFor="finance-to" className="sr-only">Até</label>
              <Input id="finance-to" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="h-10 min-w-0 border-0 bg-slate-50 text-xs font-semibold shadow-none sm:min-w-36" />
            </div>
          </div>
        </div>
      </header>

      <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-38px_rgba(15,23,42,0.5)]">
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-7">
          <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Visão geral</p><CardTitle className="mt-1 text-xl">Resumo do caixa</CardTitle></div>
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-50 text-brand-600"><WalletCards className="h-5 w-5" aria-hidden="true" /></span>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 sm:p-6 md:grid-cols-3">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-100 bg-emerald-50/70 p-5">
            <span className="mb-5 grid h-10 w-10 place-items-center rounded-xl bg-white text-emerald-600 shadow-sm"><ArrowDownLeft className="h-5 w-5" aria-hidden="true" /></span>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-700/70">Entradas</p>
            <p className="mt-1 text-2xl font-black tracking-tight text-slate-950 sm:text-3xl">
              {data ? formatBRL(data.summary.total_in_cents) : "—"}
            </p>
            <p className="mt-2 text-xs text-emerald-800/60">Valores recebidos no período</p>
          </div>
          <div className="rounded-2xl border border-rose-100 bg-rose-50/70 p-5">
            <span className="mb-5 grid h-10 w-10 place-items-center rounded-xl bg-white text-rose-600 shadow-sm"><ArrowUpRight className="h-5 w-5" aria-hidden="true" /></span>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-rose-700/70">Saídas</p>
            <p className="mt-1 text-2xl font-black tracking-tight text-slate-950 sm:text-3xl">
              {data ? formatBRL(data.summary.total_out_cents) : "—"}
            </p>
            <p className="mt-2 text-xs text-rose-800/60">Devoluções e ajustes de saída</p>
          </div>
          <div className="relative overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-br from-white via-slate-50 to-brand-50/70 p-5">
            <div className="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-brand-200/35 blur-2xl" aria-hidden="true" />
            <span className="relative mb-5 grid h-10 w-10 place-items-center rounded-xl border border-brand-100 bg-white text-brand-600 shadow-sm"><WalletCards className="h-5 w-5" aria-hidden="true" /></span>
            <p className="relative text-xs font-bold uppercase tracking-[0.14em] text-brand-700/70">Saldo líquido</p>
            <p className="relative mt-1 text-2xl font-black tracking-tight text-slate-950 sm:text-3xl">
              {data ? formatBRL(data.summary.net_cents) : "—"}
            </p>
            <p className="relative mt-2 text-xs text-slate-500">Resultado consolidado do período</p>
          </div>
        </CardContent>
      </Card>

      <ManualPaymentsPanel fromDate={fromDate} toDate={toDate} />

      <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-42px_rgba(15,23,42,0.5)]">
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-7">
          <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Extrato</p><CardTitle className="mt-1 text-xl">Movimentações do caixa</CardTitle></div>
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-slate-100 text-slate-600"><ReceiptText className="h-5 w-5" aria-hidden="true" /></span>
        </CardHeader>
        <CardContent className="space-y-4 p-4 sm:p-6">


          {isLoading && <LoadingExperience label="Buscando movimentações" compact />}
          {isError && (
            <p className="text-sm text-red-600">Erro ao carregar movimentos.</p>
          )}

          <Table mobileCards containerClassName="rounded-2xl border border-slate-200/80">
            <TableHeader className="bg-slate-50/80">
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
                <TableRow key={movement.id} className="hover:bg-slate-50/70">
                  <TableCell mobileLabel="Tipo"><span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${movement.type === "in" ? "bg-emerald-50 text-emerald-700" : movement.type === "out" ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-600"}`}>{movement.type === "in" ? <ArrowDownLeft className="h-3.5 w-3.5" aria-hidden="true" /> : <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />}{movement.type === "in" ? "Entrada" : movement.type === "out" ? "Saída" : movement.type}</span></TableCell>
                  <TableCell mobileLabel="Categoria">{({ sale: "Venda", fee: "Taxa", refund: "Devolução", adjustment: "Ajuste" } as Record<string, string>)[movement.category] ?? movement.category}</TableCell>
                  <TableCell mobileLabel="Descrição">{movement.description ?? "-"}</TableCell>
                  <TableCell mobileLabel="Valor" className="font-bold text-slate-950">
                    {formatBRL(movement.amount_cents)}
                  </TableCell>
                  <TableCell mobileLabel="Data">
                    {new Date(movement.occurred_at).toLocaleString("pt-BR")}
                  </TableCell>
                </TableRow>
              ))}
              {!isLoading && !data?.movements?.length && <TableRow><TableCell colSpan={5} className="py-12 text-center"><span className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-400"><ReceiptText className="h-5 w-5" aria-hidden="true" /></span><p className="font-semibold text-slate-700">Nenhuma movimentação no período</p><p className="mt-1 text-xs text-slate-400">Quando houver entradas ou saídas, elas aparecerão aqui.</p></TableCell></TableRow>}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
