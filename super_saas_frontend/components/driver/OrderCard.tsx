import { t } from "@/i18n/translate";
import { DriverOrder } from "@/services/driverApi";

export default function OrderCard({ order, onAccept }: { order: DriverOrder; onAccept: () => void }) {
  return (
    <article className="mb-3 rounded-lg border p-3">
      <p className="font-semibold">{t("order")} #{order.id}</p>
      <p className="text-sm">{order.customer_name}</p>
      <p className="text-sm text-gray-600">{order.address}</p>
      <button onClick={onAccept} className="mt-3 w-full rounded bg-green-600 px-4 py-3 text-white">
        {t("accept_delivery").toUpperCase()}
      </button>
    </article>
  );
}
