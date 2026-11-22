"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Check, Coins, Gift, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { api } from "@/lib/api";

interface LoyaltySettings { points_enabled: boolean; reais_por_ponto: number; points_expiration_days: number | null }

export default function LoyaltyPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["marketing", "loyalty"], queryFn: () => api.get<LoyaltySettings>("/api/admin/marketing/loyalty") });
  const [form, setForm] = useState({ points_enabled: true, reais_por_ponto: 1, points_expiration_days: "" });
  useEffect(() => { if (data) setForm({ points_enabled: data.points_enabled, reais_por_ponto: data.reais_por_ponto, points_expiration_days: data.points_expiration_days?.toString() ?? "" }); }, [data]);
  const mutation = useMutation({ mutationFn: () => api.put("/api/admin/marketing/loyalty", { points_enabled: form.points_enabled, reais_por_ponto: Number(form.reais_por_ponto || 0), points_expiration_days: form.points_expiration_days ? Number(form.points_expiration_days) : null }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["marketing", "loyalty"] }) });
  const spend = Number(form.reais_por_ponto || 0);

  return <div className="mx-auto max-w-[1500px] space-y-6 pb-10">
    <header><div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-600"><Sparkles className="h-4 w-4" />Marketing</div><h1 className="text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">Programa de fidelidade</h1><p className="mt-2 max-w-2xl text-sm text-slate-500">Transforme cada pedido em motivo para o cliente voltar ao seu restaurante.</p></header>
    {isLoading ? <LoadingExperience label="Preparando a fidelidade" compact /> : <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,.65fr)]">
      <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-42px_rgba(15,23,42,0.55)]">
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-7"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Configuração</p><CardTitle className="mt-1 text-xl">Regras de pontuação</CardTitle></div><span className="grid h-11 w-11 place-items-center rounded-2xl bg-amber-50 text-amber-600"><Coins className="h-5 w-5" /></span></CardHeader>
        <CardContent className="space-y-6 p-4 sm:p-6">
          <button type="button" role="switch" aria-checked={form.points_enabled} onClick={() => setForm((p) => ({ ...p, points_enabled: !p.points_enabled }))} className={`flex w-full items-center justify-between rounded-2xl border p-4 text-left transition ${form.points_enabled ? "border-emerald-200 bg-emerald-50/70" : "border-slate-200 bg-slate-50"}`}><div><p className="font-bold text-slate-900">Programa de pontos</p><p className="mt-1 text-xs text-slate-500">{form.points_enabled ? "Seus clientes estão acumulando pontos" : "Ative para começar a premiar seus clientes"}</p></div><span className={`relative h-7 w-12 rounded-full transition ${form.points_enabled ? "bg-emerald-500" : "bg-slate-300"}`}><span className={`absolute top-1 grid h-5 w-5 place-items-center rounded-full bg-white shadow transition ${form.points_enabled ? "left-6" : "left-1"}`}>{form.points_enabled && <Check className="h-3 w-3 text-emerald-600" />}</span></span></button>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2"><label htmlFor="reais-point" className="text-sm font-bold text-slate-700">Valor para ganhar 1 ponto</label><div className="relative"><span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm font-bold text-slate-400">R$</span><Input id="reais-point" type="number" min="0" step="0.1" value={form.reais_por_ponto} onChange={(e) => setForm((p) => ({ ...p, reais_por_ponto: Number(e.target.value) }))} className="h-12 rounded-xl bg-slate-50/70 pl-12 font-semibold" /></div><p className="text-xs text-slate-400">Quanto o cliente precisa gastar.</p></div>
            <div className="space-y-2"><label htmlFor="points-expiry" className="text-sm font-bold text-slate-700">Validade dos pontos</label><div className="relative"><CalendarClock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input id="points-expiry" type="number" min="1" value={form.points_expiration_days} onChange={(e) => setForm((p) => ({ ...p, points_expiration_days: e.target.value }))} placeholder="Sem expiração" className="h-12 rounded-xl bg-slate-50/70 pl-11 font-semibold" /></div><p className="text-xs text-slate-400">Deixe vazio para não expirar.</p></div>
          </div>
          <Button className="h-12 rounded-xl px-6 font-bold" onClick={() => mutation.mutate()} disabled={mutation.isPending || spend <= 0}>{mutation.isPending ? "Salvando..." : "Salvar configurações"}</Button>
        </CardContent>
      </Card>
      <Card className="relative overflow-hidden rounded-[28px] border-brand-100 bg-gradient-to-br from-white via-brand-50/50 to-amber-50/60 shadow-[0_20px_55px_-42px_rgba(220,38,38,0.45)]">
        <div className="absolute -right-12 -top-12 h-40 w-40 rounded-full bg-brand-200/30 blur-3xl" />
        <CardContent className="relative p-6 sm:p-7"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-brand-600 shadow-sm"><Gift className="h-6 w-6" /></span><p className="mt-8 text-xs font-bold uppercase tracking-[0.16em] text-brand-600">Como o cliente verá</p><h2 className="mt-2 text-2xl font-black tracking-tight text-slate-950">1 ponto a cada {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(spend || 0)}</h2><p className="mt-3 text-sm leading-6 text-slate-500">{form.points_enabled ? `Os pontos ${form.points_expiration_days ? `expiram em ${form.points_expiration_days} dias` : "não expiram"} e ficam disponíveis na conta do cliente.` : "Ative o programa para esta regra começar a valer."}</p><div className="mt-7 rounded-2xl border border-white/80 bg-white/70 p-4 backdrop-blur"><p className="text-xs font-semibold text-slate-500">Exemplo em um pedido de R$ 100</p><p className="mt-1 text-xl font-black text-slate-950">+ {spend > 0 ? Math.floor(100 / spend) : 0} pontos</p></div></CardContent>
      </Card>
    </div>}
  </div>;
}
