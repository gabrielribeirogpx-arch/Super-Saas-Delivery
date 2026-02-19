"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";

interface KdsItem {
  id: number;
  name: string;
  quantity: number;
  modifiers?: Array<{ name: string }>;
  production_area?: string;
}

interface KdsOrder {
  id: number;
  status: string;
  created_at: string;
  items: KdsItem[];
}

const areas = ["COZINHA", "BAR", "FRITURA", "DOCES"];

export default function KdsPage() {
  const queryClient = useQueryClient();
  const [area, setArea] = useState("COZINHA");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["kds", area],
    queryFn: () =>
      api.get<KdsOrder[]>(`/api/kds/orders&area=${area}`),
    refetchInterval: 5000,
  });

  const startMutation = useMutation({
    mutationFn: (orderId: number) =>
      api.post(`/api/kds/orders/${orderId}/start&area=${area}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kds", area] }),
  });

  const readyMutation = useMutation({
    mutationFn: (orderId: number) =>
      api.post(`/api/kds/orders/${orderId}/ready&area=${area}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kds", area] }),
  });

  const handleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      document.documentElement.requestFullscreen();
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={area} onChange={(event) => setArea(event.target.value)}>
          {areas.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
        <Button variant="outline" onClick={handleFullscreen}>
          Modo KDS
        </Button>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Carregando KDS...</p>}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
          Erro ao carregar pedidos do KDS.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data?.map((order) => (
          <Card key={order.id} className="border-l-4 border-l-brand-500">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Pedido #{order.id}</CardTitle>
                <Badge variant="secondary">{order.status}</Badge>
              </div>
              <p className="text-xs text-slate-500">
                {new Date(order.created_at).toLocaleString("pt-BR")}
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              <ul className="space-y-2 text-sm">
                {order.items.map((item) => (
                  <li key={item.id} className="rounded-md bg-slate-50 p-2">
                    <div className="flex items-center justify-between">
                      <span>
                        {item.quantity}x {item.name}
                      </span>
                      {item.production_area && (
                        <Badge variant="outline">{item.production_area}</Badge>
                      )}
                    </div>
                    {item.modifiers?.length ? (
                      <p className="text-xs text-slate-500">
                        {item.modifiers.map((mod) => mod.name).join(", ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => startMutation.mutate(order.id)}
                >
                  Iniciar
                </Button>
                <Button size="sm" onClick={() => readyMutation.mutate(order.id)}>
                  Finalizar
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
