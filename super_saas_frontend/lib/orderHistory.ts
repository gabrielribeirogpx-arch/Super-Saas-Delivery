export interface OrderHistoryFilters {
  order: string;
  customer: string;
  status: string;
  payment: string;
  delivery: string;
  date: string;
}

export interface OrderHistoryOverview {
  total: number;
  summary: { today: number; pending: number; preparing: number; delivering: number; completed: number };
  payments: string[];
  deliveries: string[];
}

export function orderHistoryQuery(filters: OrderHistoryFilters, page: number, pageSize = 8) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  for (const [field, key] of Object.entries({ order: "order_number", customer: "customer", status: "status", payment: "payment", delivery: "delivery", date: "created_on" })) {
    const value = filters[field as keyof OrderHistoryFilters];
    if (value) params.set(key, value);
  }
  return params.toString();
}

export function orderOverviewQuery(now = new Date()) {
  const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return new URLSearchParams({ today: day, utc_offset_minutes: String(now.getTimezoneOffset()) }).toString();
}
