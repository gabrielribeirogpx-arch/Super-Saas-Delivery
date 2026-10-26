export interface DailyPerformance {
  bucket: string;
  revenue: number;
  orders: number;
}

export interface PerformanceBucket {
  start: string;
  end: string;
  revenueCents: number;
  orders: number;
}

const DAY = 86_400_000;
const iso = (time: number) => new Date(time).toISOString().slice(0, 10);
function date(value: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && iso(time) === value ? time : NaN;
}

/** Calendar buckets clipped to the selected range; money is summed in cents. */
export function mobilePerformance(
  points: DailyPerformance[],
  start: string,
  end: string,
) {
  const first = date(start),
    last = date(end);
  const days = Math.round((last - first) / DAY) + 1;
  const unit = days <= 31 ? "day" : days <= 180 ? "week" : "month";
  const buckets: PerformanceBucket[] = [];
  if (!Number.isFinite(days) || days < 1) return { unit, buckets };
  for (let cursor = first; cursor <= last; ) {
    const current = new Date(cursor);
    const next =
      unit === "month"
        ? Date.UTC(current.getUTCFullYear(), current.getUTCMonth() + 1, 1)
        : cursor + (unit === "week" ? 7 : 1) * DAY;
    buckets.push({
      start: iso(cursor),
      end: iso(Math.min(next - DAY, last)),
      revenueCents: 0,
      orders: 0,
    });
    cursor = next;
  }
  const monthly = new Map(
    buckets.map((bucket, index) => [bucket.start.slice(0, 7), index]),
  );
  for (const point of points) {
    const time = date(point.bucket);
    if (!Number.isFinite(time) || time < first || time > last) continue;
    const index =
      unit === "month"
        ? monthly.get(point.bucket.slice(0, 7))
        : Math.floor((time - first) / (DAY * (unit === "week" ? 7 : 1)));
    if (index === undefined || !buckets[index]) continue;
    const revenue = Number(point.revenue),
      orders = Number(point.orders);
    if (Number.isFinite(revenue))
      buckets[index].revenueCents += Math.round(revenue * 100);
    if (Number.isFinite(orders)) buckets[index].orders += orders;
  }
  return { unit, buckets };
}
