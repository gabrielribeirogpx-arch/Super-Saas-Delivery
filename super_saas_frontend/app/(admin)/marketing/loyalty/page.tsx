"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function LoyaltyPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["marketing", "loyalty"],
    queryFn: () => api.get<{ points_enabled: boolean; reais_por_ponto: number; points_expiration_days: number | null }>("/api/admin/marketing/loyalty"),
  });

  const [form, setForm] = useState({ points_enabled: true, reais_por_ponto: 1, points_expiration_days: "" });

  const mutation = useMutation({
    mutationFn: () =>
      api.put("/api/admin/marketing/loyalty", {
        points_enabled: form.points_enabled,
        reais_por_ponto: Number(form.reais_por_ponto || 0),
        points_expiration_days: form.points_expiration_days ? Number(form.points_expiration_days) : null,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["marketing", "loyalty"] }),
  });

  const current = data ?? {
    points_enabled: form.points_enabled,
    reais_por_ponto: Number(form.reais_por_ponto || 1),
    points_expiration_days: form.points_expiration_days ? Number(form.points_expiration_days) : null,
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Marketing • Loyalty</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <p className="text-sm text-slate-500">Carregando configuração...</p>}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.points_enabled}
            onChange={(e) => setForm((prev) => ({ ...prev, points_enabled: e.target.checked }))}
          />
          Habilitar pontos
        </label>
        <div>
          <p className="mb-1 text-xs text-slate-500">Valor gasto para ganhar 1 ponto</p>
          <Input
            type="number"
            min="0"
            step="0.1"
            value={form.reais_por_ponto}
            onChange={(e) => setForm((prev) => ({ ...prev, reais_por_ponto: Number(e.target.value) }))}
          />
        </div>
        <div>
          <p className="mb-1 text-xs text-slate-500">Expiração dos pontos (dias)</p>
          <Input
            type="number"
            min="1"
            value={form.points_expiration_days}
            onChange={(e) => setForm((prev) => ({ ...prev, points_expiration_days: e.target.value }))}
            placeholder="Opcional"
          />
        </div>
        <p className="text-xs text-slate-500">Exemplo: se você colocar 10, o cliente ganha 1 ponto a cada R$10 gastos.</p>
        <p className="text-sm text-slate-600">Atual: 1 ponto a cada R${current.reais_por_ponto} gastos.</p>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>Salvar</Button>
      </CardContent>
    </Card>
  );
}
