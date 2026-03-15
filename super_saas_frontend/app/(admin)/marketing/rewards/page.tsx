"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

export default function RewardsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ points_required: "100", discount_value: "10" });
  const { data } = useQuery({ queryKey: ["marketing", "rewards"], queryFn: () => api.get<any[]>("/api/admin/marketing/rewards") });
  const mutation = useMutation({
    mutationFn: () => api.post("/api/admin/marketing/rewards", { points_required: Number(form.points_required), discount_value: Number(form.discount_value) }),
    onSuccess: () => {
      setForm({ points_required: "100", discount_value: "10" });
      queryClient.invalidateQueries({ queryKey: ["marketing", "rewards"] });
    },
  });

  return (
    <Card>
      <CardHeader><CardTitle>Marketing • Rewards</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 md:grid-cols-2">
          <Input type="number" placeholder="Pontos necessários" value={form.points_required} onChange={(e) => setForm((p) => ({ ...p, points_required: e.target.value }))} />
          <Input type="number" placeholder="Desconto (R$)" value={form.discount_value} onChange={(e) => setForm((p) => ({ ...p, discount_value: e.target.value }))} />
        </div>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>Criar recompensa</Button>
        <Table>
          <TableHeader><TableRow><TableHead>Pontos</TableHead><TableHead>Desconto</TableHead></TableRow></TableHeader>
          <TableBody>
            {(data ?? []).map((reward) => (
              <TableRow key={reward.id}><TableCell>{reward.points_required}</TableCell><TableCell>{reward.discount_value}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
