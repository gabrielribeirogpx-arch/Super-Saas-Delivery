"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Coins, Gift, Plus, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

interface Reward { id: number; points_required: number; discount_value: number }
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export default function RewardsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ points_required: "100", discount_value: "10" });
  const { data } = useQuery({ queryKey: ["marketing", "rewards"], queryFn: () => api.get<Reward[]>("/api/admin/marketing/rewards") });
  const createMutation = useMutation({ mutationFn: () => api.post("/api/admin/marketing/rewards", { points_required: Number(form.points_required), discount_value: Number(form.discount_value) }), onSuccess: () => { setForm({ points_required: "100", discount_value: "10" }); queryClient.invalidateQueries({ queryKey: ["marketing", "rewards"] }); } });
  const deleteMutation = useMutation({ mutationFn: (id: number) => api.delete(`/api/admin/marketing/rewards/${id}`), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["marketing", "rewards"] }) });
  const rewards = data ?? [];
  const isValid = Number(form.points_required) > 0 && Number(form.discount_value) > 0;

  return <div className="mx-auto max-w-[1500px] space-y-6 pb-10">
    <header><div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-600"><Sparkles className="h-4 w-4" />Marketing</div><h1 className="text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">Recompensas</h1><p className="mt-2 max-w-2xl text-sm text-slate-500">Converta os pontos acumulados em benefícios que trazem seus clientes de volta.</p></header>
    <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-42px_rgba(15,23,42,0.55)]">
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-7"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Novo benefício</p><CardTitle className="mt-1 text-xl">Criar recompensa</CardTitle></div><span className="grid h-11 w-11 place-items-center rounded-2xl bg-amber-50 text-amber-600"><Gift className="h-5 w-5" /></span></CardHeader>
      <CardContent className="p-4 sm:p-6"><div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
        <div className="space-y-2"><label htmlFor="points_required" className="text-sm font-bold text-slate-700">Pontos necessários</label><div className="relative"><Coins className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-amber-500" /><Input id="points_required" type="number" min="1" value={form.points_required} onChange={(e) => setForm((p) => ({ ...p, points_required: e.target.value }))} className="h-12 rounded-xl bg-slate-50/70 pl-11 font-semibold" /></div></div>
        <div className="space-y-2"><label htmlFor="discount_value" className="text-sm font-bold text-slate-700">Desconto concedido</label><div className="relative"><span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm font-bold text-slate-400">R$</span><Input id="discount_value" type="number" min="0.01" step="0.01" value={form.discount_value} onChange={(e) => setForm((p) => ({ ...p, discount_value: e.target.value }))} className="h-12 rounded-xl bg-slate-50/70 pl-12 font-semibold" /></div></div>
        <Button className="h-12 rounded-xl px-6 font-bold" onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !isValid}><Plus className="mr-2 h-4 w-4" />{createMutation.isPending ? "Adicionando..." : "Adicionar recompensa"}</Button>
      </div></CardContent>
    </Card>
    <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-42px_rgba(15,23,42,0.5)]">
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-7"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Catálogo</p><CardTitle className="mt-1 text-xl">Recompensas disponíveis</CardTitle></div><span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600">{rewards.length} {rewards.length === 1 ? "opção" : "opções"}</span></CardHeader>
      <CardContent className="p-4 sm:p-6"><Table mobileCards containerClassName="rounded-2xl border border-slate-200/80"><TableHeader className="bg-slate-50/80"><TableRow><TableHead>Pontos necessários</TableHead><TableHead>Benefício</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader><TableBody>
        {rewards.map((reward) => <TableRow key={reward.id} className="hover:bg-slate-50/70"><TableCell mobileLabel="Pontos necessários"><span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-sm font-black text-amber-700"><Coins className="h-4 w-4" />{reward.points_required} pontos</span></TableCell><TableCell mobileLabel="Benefício"><span className="font-black text-slate-950">{money.format(Number(reward.discount_value ?? 0))} de desconto</span></TableCell><TableCell mobileLabel="Ações" mobileActions className="text-right"><button type="button" aria-label={`Excluir recompensa de ${reward.points_required} pontos`} className="delete-reward inline-flex h-9 items-center gap-2 rounded-xl px-3 text-sm font-bold text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50" onClick={() => deleteMutation.mutate(Number(reward.id))} disabled={deleteMutation.isPending && deleteMutation.variables === Number(reward.id)}><Trash2 className="h-4 w-4" />Excluir</button></TableCell></TableRow>)}
        {!rewards.length && <TableRow><TableCell colSpan={3} className="py-12 text-center"><span className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-400"><Gift className="h-5 w-5" /></span><p className="font-semibold text-slate-700">Nenhuma recompensa cadastrada</p><p className="mt-1 text-xs text-slate-400">Crie um benefício para seus clientes resgatarem.</p></TableCell></TableRow>}
      </TableBody></Table></CardContent>
    </Card>
  </div>;
}
