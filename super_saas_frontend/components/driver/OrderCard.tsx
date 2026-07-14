import { t } from "@/i18n/translate";
import { DriverOrder } from "@/services/driverApi";

type Props = { order: DriverOrder; onAccept?: () => void; onOpen?: () => void };

function money(cents?: number | null) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format((cents || 0) / 100);
}

export default function OrderCard({ order, onAccept, onOpen }: Props) {
  const hasCoords = Number.isFinite(order.destination_lat ?? order.customer_lat) && Number.isFinite(order.destination_lng ?? order.customer_lng);
  return (
    <article className="mb-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-bold text-slate-950">Pedido #{order.daily_order_number ?? order.id}</p>
          <p className="text-sm font-medium text-slate-700">{order.customer_name}</p>
          {order.neighborhood && <p className="text-xs text-slate-500">Bairro: {order.neighborhood}</p>}
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{order.status}</span>
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-slate-600">{order.address}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
        <span>Valor: <strong>{money(order.total_cents)}</strong></span>
        <span>Pagamento: <strong>{order.payment_method || "--"}</strong></span>
        <span>Tipo: <strong>{order.order_type || "delivery"}</strong></span>
        <span>{hasCoords ? "Coordenadas disponíveis" : "Sem coordenadas"}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {onOpen && <button onClick={onOpen} className="rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700">Detalhes</button>}
        {onAccept && <button onClick={onAccept} className="rounded-xl bg-green-600 px-4 py-3 text-sm font-bold text-white">{t("accept_delivery").toUpperCase()}</button>}
      </div>
    </article>
  );
}
