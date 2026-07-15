"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { AlertTriangle, Bike, CheckCircle2, Clock3, Home, ListChecks, LocateFixed, MapPinned, Menu, PackageCheck, PackageOpen, Route, UserRound, Wifi, WifiOff } from "lucide-react";

export const statusLabels: Record<string, string> = {
  AVAILABLE: "Disponível",
  READY_FOR_DELIVERY: "Pronto para entrega",
  ACCEPTED: "Aceita",
  DRIVER_ASSIGNED: "Aceita",
  OUT_FOR_DELIVERY: "Em rota",
  IN_TRANSIT: "Em rota",
  PICKED_UP: "Em rota",
  ARRIVED: "Chegou ao destino",
  DELIVERED: "Entregue",
  FAILED: "Problema",
  CANCELLED: "Cancelada",
};

export function driverStatusLabel(status?: string | null) {
  return status ? statusLabels[status] ?? status.split("_").join(" ").toLowerCase().replace(/^./, (c) => c.toUpperCase()) : "--";
}

export function DriverStatusBadge({ status }: { status?: string | null }) {
  const danger = ["FAILED", "CANCELLED"].includes(status || "");
  const done = status === "DELIVERED";
  const moving = ["OUT_FOR_DELIVERY", "IN_TRANSIT", "PICKED_UP", "ARRIVED"].includes(status || "");
  const cls = danger ? "bg-red-50 text-red-700 ring-red-200" : done ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : moving ? "bg-orange-50 text-orange-700 ring-orange-200" : "bg-blue-50 text-blue-700 ring-blue-200";
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${cls}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{driverStatusLabel(status)}</span>;
}

export function DriverConnectionStatus({ offline, gpsActive, reconnecting }: { offline?: boolean; gpsActive?: boolean; reconnecting?: boolean }) {
  const label = offline ? "Offline" : reconnecting ? "Reconectando" : gpsActive ? "GPS ativo" : "Online";
  const Icon = offline ? WifiOff : gpsActive ? LocateFixed : Wifi;
  const color = offline ? "text-red-700 bg-red-50" : reconnecting ? "text-amber-700 bg-amber-50" : gpsActive ? "text-emerald-700 bg-emerald-50" : "text-emerald-700 bg-emerald-50";
  return <span className={`inline-flex min-h-8 items-center gap-1.5 rounded-full px-2.5 text-xs font-bold ${color}`}><Icon className="h-3.5 w-3.5" aria-hidden />{label}</span>;
}

export function DriverHeader({ title, name, offline, gpsActive, onLogout }: { title: string; name?: string; offline?: boolean; gpsActive?: boolean; onLogout: () => void }) {
  return <header className="sticky top-0 z-40 -mx-4 mb-4 border-b border-slate-200/80 bg-white/90 px-4 pb-3 pt-[max(.75rem,env(safe-area-inset-top))] shadow-sm backdrop-blur supports-[backdrop-filter]:bg-white/75 sm:mx-0 sm:rounded-b-3xl">
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-emerald-600 text-white shadow-lg shadow-emerald-200"><Bike className="h-5 w-5" /></div><div className="min-w-0"><p className="truncate text-base font-black text-slate-950">{title}</p><p className="truncate text-xs font-semibold text-slate-500">Service Delivery{name ? ` • ${name}` : ""}</p></div></div>
      <div className="flex items-center gap-2"><DriverConnectionStatus offline={offline} gpsActive={gpsActive} /><details className="relative"><summary aria-label="Abrir menu do perfil" className="grid h-11 w-11 cursor-pointer list-none place-items-center rounded-2xl border border-slate-200 bg-white text-slate-700 shadow-sm [&::-webkit-details-marker]:hidden"><Menu className="h-5 w-5" /></summary><div className="absolute right-0 mt-2 w-44 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl"><Link href="/driver/dashboard" className="block rounded-xl px-3 py-2 text-sm font-semibold text-slate-700">Início</Link><button onClick={onLogout} className="block w-full rounded-xl px-3 py-2 text-left text-sm font-bold text-red-600">Sair</button></div></details></div>
    </div>
  </header>;
}

export function DriverStatCard({ icon, value, title, tone="emerald", href }: { icon: ReactNode; value: number; title: string; tone?: "emerald"|"blue"|"orange"|"slate"; href?: string }) {
  const tones = { emerald: "bg-emerald-50 text-emerald-700", blue: "bg-blue-50 text-blue-700", orange: "bg-orange-50 text-orange-700", slate: "bg-slate-100 text-slate-700" };
  const body = <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm transition active:scale-[.98]"><div className={`mb-3 grid h-10 w-10 place-items-center rounded-2xl ${tones[tone]}`}>{icon}</div><strong className="block text-3xl font-black leading-none text-slate-950">{value}</strong><span className="mt-1 block text-sm font-bold text-slate-600">{title}</span></div>;
  return href ? <Link href={href}>{body}</Link> : body;
}

export function DriverEmptyState({ title, message }: { title: string; message: string }) {
  return <div className="mb-4 rounded-3xl border border-dashed border-slate-300 bg-white p-6 text-center shadow-sm"><div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-3xl bg-slate-100 text-slate-500"><PackageOpen className="h-7 w-7" /></div><p className="font-black text-slate-900">{title}</p><p className="mt-1 text-sm leading-6 text-slate-600">{message}</p></div>;
}

export function DriverBottomNav({ active="home", hasRoute=false }: { active?: "home"|"deliveries"|"route"|"profile"; hasRoute?: boolean }) {
  const item = (key: typeof active, href: string, label: string, icon: ReactNode, disabled=false) => <Link aria-disabled={disabled} href={disabled ? "#" : href} className={`flex min-h-11 flex-1 flex-col items-center justify-center gap-1 rounded-2xl text-[11px] font-bold ${active===key ? "bg-emerald-50 text-emerald-700" : disabled ? "pointer-events-none text-slate-300" : "text-slate-500"}`}>{icon}{label}</Link>;
  return <nav className="fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white/95 px-3 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-10px_30px_rgba(15,23,42,.08)] backdrop-blur md:hidden"> <div className="mx-auto flex max-w-md gap-1">{item("home","/driver/dashboard","Início",<Home className="h-5 w-5"/>)}{item("deliveries","/driver/deliveries","Entregas",<ListChecks className="h-5 w-5"/>)}{item("route","/driver/deliveries","Rota",<Route className="h-5 w-5"/>,!hasRoute)}{item("profile","/driver/dashboard","Perfil",<UserRound className="h-5 w-5"/>)}</div></nav>;
}

export { AlertTriangle, CheckCircle2, Clock3, MapPinned, PackageCheck };
