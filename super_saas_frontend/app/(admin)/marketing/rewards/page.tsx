"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

export default function RewardsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ points_required: "100", discount_value: "10" });

  const { data } = useQuery({
    queryKey: ["marketing", "rewards"],
    queryFn: () => api.get<any[]>("/api/admin/marketing/rewards"),
  });

  const createRewardMutation = useMutation({
    mutationFn: () =>
      api.post("/api/admin/marketing/rewards", {
        points_required: Number(form.points_required),
        discount_value: Number(form.discount_value),
      }),
    onSuccess: () => {
      setForm({ points_required: "100", discount_value: "10" });
      queryClient.invalidateQueries({ queryKey: ["marketing", "rewards"] });
    },
  });

  const deleteRewardMutation = useMutation({
    mutationFn: (rewardId: number) => api.delete(`/api/admin/marketing/rewards/${rewardId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["marketing", "rewards"] });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Marketing • Recompensas</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label htmlFor="points_required" className="text-sm font-medium">
              Pontos necessários
            </label>
            <Input
              id="points_required"
              type="number"
              value={form.points_required}
              onChange={(e) => setForm((p) => ({ ...p, points_required: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="discount_value" className="text-sm font-medium">
              Desconto (R$)
            </label>
            <Input
              id="discount_value"
              type="number"
              value={form.discount_value}
              onChange={(e) => setForm((p) => ({ ...p, discount_value: e.target.value }))}
            />
          </div>
        </div>
        <Button onClick={() => createRewardMutation.mutate()} disabled={createRewardMutation.isPending}>
          Adicionar recompensa
        </Button>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Pontos necessários</TableHead>
              <TableHead>Desconto</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((reward) => (
              <TableRow key={reward.id}>
                <TableCell>{reward.points_required}</TableCell>
                <TableCell>{currencyFormatter.format(Number(reward.discount_value ?? 0))}</TableCell>
                <TableCell className="text-right">
                  <button
                    type="button"
                    className="delete-reward text-sm font-medium text-red-600 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => deleteRewardMutation.mutate(Number(reward.id))}
                    disabled={deleteRewardMutation.isPending && deleteRewardMutation.variables === Number(reward.id)}
                  >
                    Excluir
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
