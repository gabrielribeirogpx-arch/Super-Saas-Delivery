"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Home, LocateFixed, MapPinned, Menu, PackageCheck, PackageOpen, Route, Truck, Wifi, WifiOff, XCircle } from "lucide-react";
import styles from "./Driver.module.css";

export const statusLabels: Record<string, string> = {
  AVAILABLE: "Disponível", READY_FOR_DELIVERY: "Pronta para retirada", ACCEPTED: "Aceita", DRIVER_ASSIGNED: "Aceita",
  OUT_FOR_DELIVERY: "Em rota", IN_TRANSIT: "Em rota", PICKED_UP: "Em rota", ARRIVED: "No destino",
  DELIVERED: "Entregue", FAILED: "Problema", CANCELLED: "Cancelada", CANCELED: "Cancelada",
};
export function driverStatusLabel(status?: string | null) {
  return status ? statusLabels[status.toUpperCase()] ?? "Status não identificado" : "Aguardando atualização";
}
export function DriverStatusBadge({ status }: { status?: string | null }) {
  const normalized = status?.toUpperCase() || "";
  const danger = ["FAILED", "CANCELLED", "CANCELED"].includes(normalized);
  const done = normalized === "DELIVERED";
  const moving = ["OUT_FOR_DELIVERY", "IN_TRANSIT", "PICKED_UP", "ARRIVED"].includes(normalized);
  const Icon = danger ? XCircle : done ? CheckCircle2 : moving ? Truck : PackageCheck;
  return <span className={styles.statusBadge} data-tone={danger ? "danger" : done ? "success" : moving ? "brand" : "neutral"}><Icon size={14} aria-hidden="true" />{driverStatusLabel(status)}</span>;
}
export function DriverConnectionStatus({ offline, gpsActive, reconnecting }: { offline?: boolean; gpsActive?: boolean; reconnecting?: boolean }) {
  const label = offline ? "Sem conexão" : reconnecting ? "Reconectando" : gpsActive ? "GPS ativo" : "Conectado";
  const Icon = offline ? WifiOff : gpsActive ? LocateFixed : Wifi;
  return <span role="status" className={styles.connection} data-offline={offline}><Icon size={14} aria-hidden="true" />{label}</span>;
}
export function DriverHeader({ title, name, offline, gpsActive, onLogout }: { title: string; name?: string; offline?: boolean; gpsActive?: boolean; onLogout: () => void }) {
  return <header className={styles.header}>
    <div className={styles.headerIdentity}><img src="/brand/fomizero-avatar-app.svg" alt="Fomizero" width={40} height={40} /><div><p className={styles.eyebrow}>ÁREA DO ENTREGADOR</p><h1>{title}</h1></div></div>
    <details className={styles.profileMenu}><summary aria-label="Abrir menu do perfil"><Menu size={21} aria-hidden="true" /></summary><div><p>{name || "Entregador"}</p><Link href="/driver/dashboard">Meu painel</Link><button type="button" onClick={onLogout}>Sair da conta</button></div></details>
    <div className={styles.headerConnection}><DriverConnectionStatus offline={offline} gpsActive={gpsActive} /></div>
  </header>;
}
export function DriverStatCard({ icon, value, title, tone="emerald", href }: { icon: ReactNode; value: number; title: string; tone?: "emerald"|"blue"|"orange"|"slate"; href?: string }) {
  const body = <div className={styles.statCard}><div className={styles.statIcon} data-tone={tone}>{icon}</div><strong>{value}</strong><span>{title}</span></div>;
  return href ? <Link className={styles.statLink} href={href}>{body}</Link> : body;
}
export function DriverEmptyState({ title, message }: { title: string; message: string }) {
  return <div className={styles.empty}><span><PackageOpen size={27} aria-hidden="true" /></span><h3>{title}</h3><p>{message}</p></div>;
}
export function DriverBottomNav({ active="home", hasRoute=false, routeId }: { active?: "home"|"deliveries"|"route"|"profile"; hasRoute?: boolean; routeId?: number }) {
  return <nav className={styles.bottomNav} aria-label="Navegação do entregador"><div>
    <Link href="/driver/dashboard" aria-current={active !== "route" ? "page" : undefined}><Home size={20} aria-hidden="true" />Meu painel</Link>
    {hasRoute && routeId ? <Link href={`/driver/deliveries/${routeId}`} aria-current={active === "route" ? "page" : undefined}><Route size={20} aria-hidden="true" />Entrega ativa</Link> : <span aria-disabled="true"><Route size={20} aria-hidden="true" />Sem entrega ativa</span>}
  </div></nav>;
}
export { AlertTriangle, CheckCircle2, Clock3, MapPinned, PackageCheck };
