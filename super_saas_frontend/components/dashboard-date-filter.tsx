import { CalendarDays } from "lucide-react";

import { Select } from "@/components/ui/select";

export type DashboardPresetOption = "today" | "yesterday" | "last7" | "last30" | "custom";

interface DashboardDateFilterProps {
  preset: DashboardPresetOption;
  start: string;
  end: string;
  onPresetChange: (value: DashboardPresetOption) => void;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
}

export function DashboardDateFilter({
  preset,
  start,
  end,
  onPresetChange,
  onStartChange,
  onEndChange,
}: DashboardDateFilterProps) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2 rounded-lg border border-slate-200 bg-white/80 p-2 text-sm shadow-sm">
      <span className="inline-flex items-center gap-1 text-slate-500">
        <CalendarDays className="h-4 w-4" />
        Período
      </span>
      <Select
        className="h-8 w-[170px] text-xs"
        value={preset}
        onChange={(event) => onPresetChange(event.target.value as DashboardPresetOption)}
        aria-label="Selecionar período do dashboard"
      >
        <option value="today">Hoje</option>
        <option value="yesterday">Ontem</option>
        <option value="last7">Últimos 7 dias</option>
        <option value="last30">Últimos 30 dias</option>
        <option value="custom">Personalizado</option>
      </Select>
      {preset === "custom" ? (
        <div className="flex items-center gap-1 text-xs">
          <input
            type="date"
            className="h-8 rounded-md border border-slate-200 px-2 text-xs"
            value={start}
            onChange={(event) => onStartChange(event.target.value)}
            aria-label="Data inicial"
          />
          <span className="text-slate-400">→</span>
          <input
            type="date"
            className="h-8 rounded-md border border-slate-200 px-2 text-xs"
            value={end}
            onChange={(event) => onEndChange(event.target.value)}
            aria-label="Data final"
          />
        </div>
      ) : null}
    </div>
  );
}
