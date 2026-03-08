"use client";

export const dynamic = "force-dynamic";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/DriverLayout";
import {
  ActiveOrder,
  completeOrder,
  getActiveDelivery,
  getDriverDeliverySnapshot,
  startOrder,
  type DriverDeliverySnapshot,
} from "@/services/delivery";

type DeliveryLoadState = {
  order: ActiveOrder | null;
  source: "snapshot" | "active" | "none";
  diagnostics: {
    lastError?: string;
    pollCount: number;
    serverTime?: string;
    outForDeliveryCount?: number;
    driverStatus?: string;
  };
};

function getErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message) {
    return err.message;
  }

  return "unknown_error";
}

export default function ActiveDeliveryPage() {
  const router = useRouter();
  const pollCountRef = useRef(0);
  const [state, setState] = useState<DeliveryLoadState>({
    order: null,
    source: "none",
    diagnostics: {
      pollCount: 0,
    },
  });

  const loadActiveDelivery = useCallback(async () => {
    pollCountRef.current += 1;
    const nextPollCount = pollCountRef.current;

    try {
      const snapshot: DriverDeliverySnapshot = await getDriverDeliverySnapshot();

      if (snapshot.activeOrder) {
        setState({
          order: snapshot.activeOrder,
          source: "snapshot",
          diagnostics: {
            pollCount: nextPollCount,
            driverStatus: snapshot.driverStatus,
            outForDeliveryCount: snapshot.outForDeliveryCount,
            serverTime: snapshot.serverTime,
          },
        });
        return;
      }

      const activeOrder = await getActiveDelivery();
      setState({
        order: activeOrder,
        source: activeOrder ? "active" : "none",
        diagnostics: {
          pollCount: nextPollCount,
          driverStatus: snapshot.driverStatus,
          outForDeliveryCount: snapshot.outForDeliveryCount,
          serverTime: snapshot.serverTime,
        },
      });
    } catch (err) {
      console.error("Active delivery loading error", err);
      setState((current) => ({
        ...current,
        order: null,
        source: "none",
        diagnostics: {
          ...current.diagnostics,
          pollCount: nextPollCount,
          lastError: getErrorMessage(err),
        },
      }));
    }
  }, []);

  useEffect(() => {
    loadActiveDelivery();

    const interval = setInterval(loadActiveDelivery, 2000);

    return () => clearInterval(interval);
  }, [loadActiveDelivery]);

  async function handleStart(activeOrder: ActiveOrder) {
    if (activeOrder.destination) {
      localStorage.setItem("driver_destination", JSON.stringify(activeOrder.destination));
    }
    localStorage.setItem("driver_active_order_id", String(activeOrder.pedido_id));

    try {
      await startOrder(activeOrder.pedido_id);
      router.push("/driver/map");
    } catch (err) {
      console.error("Start delivery error", err);
    }
  }

  async function handleComplete(orderId: number | string) {
    try {
      await completeOrder(orderId);
      await loadActiveDelivery();
    } catch (err) {
      console.error("Complete delivery error", err);
    }
  }

  const showDebug = process.env.NODE_ENV !== "production";

  const emptyMessage = useMemo(() => {
    if (state.diagnostics.lastError) {
      return "Nenhuma entrega ativa (falha ao sincronizar).";
    }

    return "Nenhuma entrega ativa.";
  }, [state.diagnostics.lastError]);

  return (
    <DriverLayout title="Entrega ativa">
      {!state.order ? (
        <div className="space-y-2">
          <p className="text-sm text-slate-500">{emptyMessage}</p>
          {state.diagnostics.lastError ? (
            <p className="text-xs text-rose-600">Erro: {state.diagnostics.lastError}</p>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">Pedido #{state.order.pedido_id}</p>
          <p className="text-sm text-slate-700">Cliente: {state.order.cliente}</p>
          <p className="text-sm text-slate-700">Endereço: {state.order.endereco}</p>
          <p className="text-sm text-slate-700">Distância: {state.order.distancia_km ?? 0} km</p>

          <div className="grid grid-cols-2 gap-2 pt-2">
            <button className="rounded bg-blue-600 py-2 text-sm text-white" onClick={() => state.order && handleStart(state.order)}>
              Iniciar entrega
            </button>
            <button
              className="rounded bg-emerald-600 py-2 text-sm text-white"
              onClick={() => handleComplete(state.order.pedido_id)}
            >
              Entregue
            </button>
          </div>
        </div>
      )}

      {showDebug ? (
        <pre className="mt-4 overflow-x-auto rounded border bg-slate-100 p-2 text-[10px] text-slate-700">
          {JSON.stringify(
            {
              source: state.source,
              diagnostics: state.diagnostics,
            },
            null,
            2,
          )}
        </pre>
      ) : null}
    </DriverLayout>
  );
}
