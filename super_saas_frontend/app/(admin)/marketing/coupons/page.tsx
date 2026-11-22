"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgePercent, Plus, Sparkles, TicketPercent } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

interface Coupon { id: number; code: string; discount_type: string; discount_value: number }
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export default function CouponsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ code: "", discount_type: "percentage", discount_value: "10" });
  const labels: Record<string, string> = { percentage: "Porcentagem", fixed: "Valor fixo" };
  const { data } = useQuery({ queryKey: ["marketing", "coupons"], queryFn: () => api.get<Coupon[]>("/api/admin/marketing/coupons") });
  const mutation = useMutation({
    mutationFn: () => api.post("/api/admin/marketing/coupons", { ...form, code: form.code.trim().toUpperCase(), discount_value: Number(form.discount_value) }),
    onSuccess: () => { setForm({ code: "", discount_type: "percentage", discount_value: "10" }); queryClient.invalidateQueries({ queryKey: ["marketing", "coupons"] }); },
  });
  const coupons = data ?? [];
  const isValid = form.code.trim().length > 0 && Number(form.discount_value) > 0;

  return <div className="mx-auto max-w-[1500px] space-y-6 pb-10">
    <header>
      <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-600"><Sparkles className="h-4 w-4" />Marketing</div>
      <h1 className="text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">Cupons</h1>
      <p className="mt-2 max-w-2xl text-sm text-slate-500">Crie incentivos para conquistar novos clientes e estimular uma próxima compra.</p>
    </header>

    <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-42px_rgba(15,23,42,0.55)]">
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-7">
        <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Nova campanha</p><CardTitle className="mt-1 text-xl">Criar cupom de desconto</CardTitle></div>
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-50 text-brand-600"><TicketPercent className="h-5 w-5" /></span>
      </CardHeader>
      <CardContent className="p-4 sm:p-6">
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1fr_auto] lg:items-end">
          <div className="space-y-2"><label htmlFor="coupon-code" className="text-sm font-bold text-slate-700">Código do cupom</label><Input id="coupon-code" placeholder="Ex.: PRIMEIRACOMPRA" value={form.code} onChange={(e) => setForm((p) => ({ ...p, code: e.target.value.toUpperCase() }))} className="h-12 rounded-xl bg-slate-50/70 font-semibold uppercase" /></div>
          <div className="space-y-2"><label htmlFor="coupon-type" className="text-sm font-bold text-slate-700">Tipo de desconto</label><select id="coupon-type" className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-3 text-sm font-medium outline-none focus:ring-2 focus:ring-brand-200" value={form.discount_type} onChange={(e) => setForm((p) => ({ ...p, discount_type: e.target.value }))}><option value="percentage">Porcentagem (%)</option><option value="fixed">Valor fixo (R$)</option></select></div>
          <div className="space-y-2"><label htmlFor="coupon-value" className="text-sm font-bold text-slate-700">Valor do desconto</label><div className="relative"><span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm font-bold text-slate-400">{form.discount_type === "percentage" ? "%" : "R$"}</span><Input id="coupon-value" type="number" min="0.01" step="0.01" value={form.discount_value} onChange={(e) => setForm((p) => ({ ...p, discount_value: e.target.value }))} className="h-12 rounded-xl bg-slate-50/70 pl-12 font-semibold" /></div></div>
          <Button className="h-12 rounded-xl px-6 font-bold shadow-sm" onClick={() => mutation.mutate()} disabled={mutation.isPending || !isValid}><Plus className="mr-2 h-4 w-4" />{mutation.isPending ? "Criando..." : "Criar cupom"}</Button>
        </div>
      </CardContent>
    </Card>

    <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-42px_rgba(15,23,42,0.5)]">
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-7">
        <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Campanhas</p><CardTitle className="mt-1 text-xl">Cupons criados</CardTitle></div>
        <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600">{coupons.length} {coupons.length === 1 ? "cupom" : "cupons"}</span>
      </CardHeader>
      <CardContent className="p-4 sm:p-6">
        <Table mobileCards containerClassName="rounded-2xl border border-slate-200/80">
          <TableHeader className="bg-slate-50/80"><TableRow><TableHead>Código</TableHead><TableHead>Tipo</TableHead><TableHead>Benefício</TableHead></TableRow></TableHeader>
          <TableBody>
            {coupons.map((coupon) => <TableRow key={coupon.id} className="hover:bg-slate-50/70"><TableCell mobileLabel="Código"><span className="inline-flex rounded-lg border border-brand-100 bg-brand-50 px-3 py-1.5 font-mono text-sm font-black tracking-wide text-brand-700">{coupon.code}</span></TableCell><TableCell mobileLabel="Tipo"><span className="text-sm font-semibold text-slate-700">{labels[coupon.discount_type] ?? coupon.discount_type}</span></TableCell><TableCell mobileLabel="Benefício"><span className="font-black text-slate-950">{coupon.discount_type === "percentage" ? `${Number(coupon.discount_value)}% OFF` : money.format(Number(coupon.discount_value))}</span></TableCell></TableRow>)}
            {!coupons.length && <TableRow><TableCell colSpan={3} className="py-12 text-center"><span className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-400"><BadgePercent className="h-5 w-5" /></span><p className="font-semibold text-slate-700">Nenhum cupom criado</p><p className="mt-1 text-xs text-slate-400">Seu primeiro cupom aparecerá aqui.</p></TableCell></TableRow>}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </div>;
}
