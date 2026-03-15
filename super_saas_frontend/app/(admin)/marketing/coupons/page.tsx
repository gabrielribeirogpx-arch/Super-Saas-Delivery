"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

export default function CouponsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ code: "", discount_type: "percentage", discount_value: "10" });
  const { data } = useQuery({ queryKey: ["marketing", "coupons"], queryFn: () => api.get<any[]>("/api/admin/marketing/coupons") });
  const mutation = useMutation({
    mutationFn: () => api.post("/api/admin/marketing/coupons", { ...form, discount_value: Number(form.discount_value) }),
    onSuccess: () => {
      setForm({ code: "", discount_type: "percentage", discount_value: "10" });
      queryClient.invalidateQueries({ queryKey: ["marketing", "coupons"] });
    },
  });

  return (
    <Card>
      <CardHeader><CardTitle>Marketing • Coupons</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 md:grid-cols-3">
          <Input placeholder="Código" value={form.code} onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))} />
          <select className="rounded-md border px-3" value={form.discount_type} onChange={(e) => setForm((p) => ({ ...p, discount_type: e.target.value }))}>
            <option value="percentage">percentage</option>
            <option value="fixed">fixed</option>
          </select>
          <Input type="number" value={form.discount_value} onChange={(e) => setForm((p) => ({ ...p, discount_value: e.target.value }))} />
        </div>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>Criar cupom</Button>
        <Table>
          <TableHeader><TableRow><TableHead>Código</TableHead><TableHead>Tipo</TableHead><TableHead>Valor</TableHead></TableRow></TableHeader>
          <TableBody>
            {(data ?? []).map((coupon) => (
              <TableRow key={coupon.id}><TableCell>{coupon.code}</TableCell><TableCell>{coupon.discount_type}</TableCell><TableCell>{coupon.discount_value}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
