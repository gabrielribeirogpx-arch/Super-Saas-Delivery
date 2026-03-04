import { AvailableOrder, ActiveOrder } from "@/services/delivery";

type Order = AvailableOrder | ActiveOrder;

export default function OrderCard({
  order,
  actionLabel,
  onAction,
}: {
  order: Order;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <article className="rounded-lg border bg-white p-4 shadow-sm">
      <p className="text-sm font-semibold">Pedido #{order.pedido_id}</p>
      {"cliente" in order && order.cliente ? (
        <p className="text-sm text-slate-700">Cliente: {order.cliente}</p>
      ) : null}
      <p className="text-sm text-slate-700">Endereço: {order.endereco}</p>
      {"distancia_km" in order ? (
        <p className="text-sm text-slate-700">Distância: {order.distancia_km} km</p>
      ) : null}

      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="mt-3 w-full rounded bg-emerald-600 px-3 py-2 text-sm font-medium text-white"
        >
          {actionLabel}
        </button>
      ) : null}
    </article>
  );
}
