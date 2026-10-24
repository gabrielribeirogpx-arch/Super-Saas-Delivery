"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, BarChart3 } from "lucide-react";
import {
  mobilePerformance,
  type DailyPerformance,
} from "@/lib/mobilePerformance";
import { cn } from "@/lib/utils";

const currency = (cents: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
    cents / 100,
  );
const dayLabel = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
const dateLabel = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
const tickLabel = (cents: number) =>
  new Intl.NumberFormat("pt-BR", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(cents / 100);

export function MobilePerformanceChart({
  points,
  start,
  end,
  available,
}: {
  points: DailyPerformance[];
  start: string;
  end: string;
  available: boolean;
}) {
  const { unit, buckets } = useMemo(
    () => mobilePerformance(points, start, end),
    [points, start, end],
  );
  const [selected, setSelected] = useState(Math.max(0, buckets.length - 1));
  const scroller = useRef<HTMLDivElement>(null);
  const [scrollable, setScrollable] = useState(false);
  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const measure = () =>
      setScrollable(element.scrollWidth > element.clientWidth + 1);
    measure();
    element.scrollLeft = element.scrollWidth;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [buckets.length, available]);

  const total = buckets.reduce((sum, bucket) => sum + bucket.revenueCents, 0);
  const totalOrders = buckets.reduce((sum, bucket) => sum + bucket.orders, 0);
  const max = Math.max(
    100,
    ...buckets.map((bucket) => Math.abs(bucket.revenueCents)),
  );
  const step = 10 ** Math.floor(Math.log10(max));
  const ceiling = Math.ceil(max / step) * step;
  const negative = buckets.some((bucket) => bucket.revenueCents < 0);
  const current = buckets[Math.min(selected, buckets.length - 1)];
  const period =
    start === end
      ? dateLabel(start)
      : start.slice(0, 4) !== end.slice(0, 4)
        ? `${dateLabel(start)} a ${dateLabel(end)}`
        : `${dayLabel(start)} a ${dayLabel(end)} · ${end.slice(0, 4)}`;
  const unitLabel = unit === "day" ? "dia" : unit === "week" ? "semana" : "mês";
  const empty = !available || !points.length || !buckets.length;

  return (
    <section
      aria-label="Gráfico de vendas no celular"
      className="min-w-0 max-w-full p-4 sm:p-5"
      data-bucket-unit={unit}
    >
      <header>
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-base font-semibold tracking-tight text-slate-950">
            Vendas no período
          </h3>
          <span className="rounded-full bg-brand-50 px-2.5 py-1 text-[10px] font-semibold text-brand-700">
            Por {unitLabel}
          </span>
        </div>
        <p className="mt-1 text-xs text-slate-500">{period}</p>
        {!empty && (
          <div className="mb-5 mt-4 flex flex-wrap items-end justify-between gap-2">
            <p className="text-[26px] font-bold tracking-tight text-slate-950">
              {currency(total)}
            </p>
            <p className="pb-1 text-xs text-slate-500">
              {totalOrders} {totalOrders === 1 ? "pedido" : "pedidos"}
            </p>
          </div>
        )}
      </header>
      {empty ? (
        <div
          role="status"
          className="mt-5 rounded-2xl bg-slate-50 p-5 text-center text-sm text-slate-500"
        >
          <BarChart3 className="mx-auto mb-2 h-6 w-6 text-slate-400" />
          Distribuição diária indisponível. Os indicadores acima continuam
          disponíveis.
        </div>
      ) : (
        <>
          <div className="flex gap-1">
            <div
              aria-hidden="true"
              className="flex h-40 w-9 shrink-0 flex-col justify-between pb-0 text-right text-[10px] text-slate-400"
            >
              <span>{tickLabel(ceiling)}</span>
              <span>{tickLabel(negative ? 0 : ceiling / 2)}</span>
              <span>{negative ? tickLabel(-ceiling) : "0"}</span>
            </div>
            <div className="relative min-w-0 flex-1">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute inset-x-0 top-0 flex h-40 flex-col justify-between"
              >
                <div className="border-t border-dashed border-slate-100" />
                <div className="border-t border-dashed border-slate-100" />
                <div className="border-t border-slate-200" />
              </div>
              <div
                ref={scroller}
                role="group"
                aria-label={`Faturamento por ${unitLabel}. Toque em uma barra para consultar.`}
                className="relative overflow-x-auto overscroll-x-contain pb-2"
              >
                <div
                  className="flex min-w-full"
                  style={{
                    width:
                      buckets.length <= 7 ? "100%" : `${buckets.length * 44}px`,
                  }}
                >
                  {buckets.map((bucket, index) => {
                    const active =
                      index === Math.min(selected, buckets.length - 1);
                    const height =
                      bucket.revenueCents === 0
                        ? 2
                        : Math.max(
                            3,
                            (Math.abs(bucket.revenueCents) / ceiling) *
                              (negative ? 76 : 152),
                          );
                    const label =
                      bucket.start === bucket.end
                        ? dateLabel(bucket.start)
                        : `${dateLabel(bucket.start)} a ${dateLabel(bucket.end)}`;
                    return (
                      <button
                        key={bucket.start}
                        type="button"
                        aria-pressed={active}
                        aria-label={`${label}: ${currency(bucket.revenueCents)}, ${bucket.orders} pedidos`}
                        onClick={() => setSelected(index)}
                        style={{ minWidth: buckets.length <= 7 ? 24 : 44 }}
                        className="group flex flex-1 flex-col items-center rounded-lg px-1 pb-1 focus-visible:outline-offset-[-2px]"
                      >
                        <span
                          aria-hidden="true"
                          className="relative block h-40 w-full"
                        >
                          <span
                            className={cn(
                              "absolute inset-x-1 rounded-t-md",
                              active
                                ? "bg-brand-600 shadow-[0_-3px_12px_rgba(220,38,38,0.12)]"
                                : bucket.revenueCents
                                  ? "bg-brand-200 group-hover:bg-brand-400"
                                  : "bg-slate-200",
                              negative &&
                                bucket.revenueCents < 0 &&
                                "rounded-b-md rounded-t-none",
                            )}
                            style={{
                              height,
                              ...(negative
                                ? bucket.revenueCents < 0
                                  ? { top: "50%" }
                                  : { bottom: "50%" }
                                : { bottom: 0 }),
                            }}
                          />
                        </span>
                        <span
                          className={cn(
                            "mt-2 text-[10px] font-medium leading-4",
                            active ? "text-brand-700" : "text-slate-500",
                          )}
                        >
                          {unit === "month" ? (
                            <>
                              {new Intl.DateTimeFormat("pt-BR", {
                                month: "short",
                                timeZone: "UTC",
                              }).format(new Date(`${bucket.start}T00:00:00Z`))}
                              <br />
                              <span className="text-[9px]">
                                {bucket.start.slice(0, 4)}
                              </span>
                            </>
                          ) : (
                            <>
                              {dayLabel(bucket.start)}
                              {bucket.end !== bucket.start && (
                                <>
                                  <br />
                                  <span className="text-[9px]">
                                    a {dayLabel(bucket.end)}
                                  </span>
                                </>
                              )}
                            </>
                          )}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
          {scrollable && (
            <p className="mt-1 flex items-center justify-end gap-1 text-[10px] text-slate-400">
              <ChevronLeft className="h-3 w-3" />
              Deslize para ver todo o período
              <ChevronRight className="h-3 w-3" />
            </p>
          )}
          <div
            aria-live="polite"
            aria-atomic="true"
            className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-3"
          >
            <p className="text-[11px] font-medium text-slate-500">
              {current.start === current.end
                ? dateLabel(current.start)
                : `${dayLabel(current.start)} a ${dateLabel(current.end)}`}
            </p>
            <div className="mt-1 flex items-center justify-between gap-2">
              <p className="text-sm font-bold text-slate-900">
                {currency(current.revenueCents)}
              </p>
              <p className="text-xs text-slate-500">
                {current.orders} {current.orders === 1 ? "pedido" : "pedidos"}
              </p>
            </div>
          </div>
          <p className="mt-3 text-[10px] leading-4 text-slate-400">
            {totalOrders === 0 ? "Nenhum pedido neste período. " : ""}
            {unit === "day"
              ? "Uma barra por dia. Toque para consultar."
              : unit === "week"
                ? "Soma a cada 7 dias, limitada ao período escolhido."
                : "Soma por mês, considerando apenas as datas escolhidas."}
          </p>
        </>
      )}
    </section>
  );
}
