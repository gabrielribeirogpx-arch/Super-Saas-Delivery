"use client";

import { MouseEvent, useMemo, useState } from "react";
import {
  AlertCircle,
  Bike,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Copy,
  CreditCard,
  FileText,
  Filter,
  MapPin,
  MessageCircle,
  MoreVertical,
  PackageCheck,
  PackageOpen,
  Phone,
  RefreshCw,
  Search,
  ShoppingBag,
  Timer,
  Truck,
  UserRound,
  X,
  XCircle,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";
import { buildOrderWhatsAppUrl, normalizeWhatsAppPhone, openOrderWhatsApp } from "@/lib/orderWhatsApp";
import { cn } from "@/lib/utils";

interface Order {
  id: number;
  tenant_id: number;
  daily_order_number?: number | null;
  tracking_token?: string | null;
  cliente_nome: string;
  cliente_telefone: string;
  customer_name?: string | null;
  customer_phone?: string | null;
  itens: string | null;
  items_json?: unknown;
  endereco: string;
  observacao?: string;
  tipo_entrega: string;
  forma_pagamento: string;
  order_type?: string | null;
  valor_total: number;
  subtotal?: number | null;
  delivery_fee?: number | null;
  total_cents?: number;
  status: string;
  payment_status?: string | null;
  change_for?: number | null;
  troco_para?: number | null;
  complemento?: string | null;
  bairro?: string | null;
  cidade?: string | null;
  referencia?: string | null;
  assigned_delivery_user_id?: number | null;
  assigned_delivery_user_name?: string | null;
  delivery_status?: string | null;
  confirmed_at?: string | null;
  preparing_at?: string | null;
  ready_at?: string | null;
  start_delivery_at?: string | null;
  delivered_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

interface OrderItem {
  id: number;
  name: string;
  quantity: number;
  unit_price_cents: number;
  subtotal_cents: number;
  notes?: string | null;
  modifiers?: Array<{ name: string; price_cents?: number }>;
  production_area?: string;
}

type StatusTone = "info" | "neutral" | "warning" | "success" | "danger";
type UpdateStatusMutation = UseMutationResult<unknown, Error, { orderId: number; status: string }, unknown>;

interface StatusPresentation {
  label: string;
  color: string;
  tone: StatusTone;
  icon: typeof Clock3;
}

const statusToneClasses: Record<StatusTone, string> = {
  info: "border-blue-200 bg-blue-50 text-blue-700",
  neutral: "border-slate-200 bg-slate-100 text-slate-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  danger: "border-red-200 bg-red-50 text-red-700",
};

const statusPresentations: Record<string, StatusPresentation> = {
  PENDING: { label: "Recebido", color: "blue", tone: "info", icon: Clock3 },
  RECEBIDO: { label: "Recebido", color: "blue", tone: "info", icon: Clock3 },
  CONFIRMADO: { label: "Confirmado", color: "blue", tone: "info", icon: CheckCircle2 },
  CONFIRMED: { label: "Confirmado", color: "blue", tone: "info", icon: CheckCircle2 },
  EM_PREPARO: { label: "Em preparo", color: "orange", tone: "warning", icon: Timer },
  PREPARANDO: { label: "Em preparo", color: "orange", tone: "warning", icon: Timer },
  PREPARING: { label: "Em preparo", color: "orange", tone: "warning", icon: Timer },
  PRONTO: { label: "Pronto para entrega", color: "green", tone: "success", icon: PackageCheck },
  READY: { label: "Pronto para entrega", color: "green", tone: "success", icon: PackageCheck },
  READY_FOR_DELIVERY: { label: "Pronto para entrega", color: "green", tone: "success", icon: PackageCheck },
  DRIVER_ASSIGNED: { label: "Entregador atribuído", color: "orange", tone: "warning", icon: Bike },
  ASSIGNED: { label: "Entregador atribuído", color: "orange", tone: "warning", icon: Bike },
  SAIU_PARA_ENTREGA: { label: "Saiu para entrega", color: "orange", tone: "warning", icon: Truck },
  OUT_FOR_DELIVERY: { label: "Saiu para entrega", color: "orange", tone: "warning", icon: Truck },
  IN_TRANSIT: { label: "Saiu para entrega", color: "orange", tone: "warning", icon: Truck },
  ENTREGUE: { label: "Entregue", color: "green", tone: "success", icon: CheckCircle2 },
  DELIVERED: { label: "Entregue", color: "green", tone: "success", icon: CheckCircle2 },
  CANCELADO: { label: "Cancelado", color: "red", tone: "danger", icon: XCircle },
  CANCELLED: { label: "Cancelado", color: "red", tone: "danger", icon: XCircle },
  FAILED: { label: "Falha na entrega", color: "red", tone: "danger", icon: AlertCircle },
};

const statusFilterOptions = ["PENDING", "CONFIRMADO", "EM_PREPARO", "PRONTO", "DRIVER_ASSIGNED", "SAIU_PARA_ENTREGA", "ENTREGUE", "CANCELADO", "FAILED"];
const statusOptions = ["RECEBIDO", "CONFIRMADO", "EM_PREPARO", "PRONTO", "SAIU_PARA_ENTREGA", "ENTREGUE", "CANCELADO"];

function getOrderStatusPresentation(status?: string | null): StatusPresentation {
  const key = (status || "").trim().toUpperCase();
  return statusPresentations[key] ?? { label: status || "Sem status", color: "gray", tone: "neutral", icon: Clock3 };
}

function getOrderNumber(order: Order) {
  return order.daily_order_number ?? order.id;
}

function getCustomerName(order: Order) {
  return order.customer_name || order.cliente_nome || "Cliente não informado";
}

function getCustomerPhone(order: Order) {
  return order.customer_phone || order.cliente_telefone || "";
}

function moneyFromCents(cents?: number | null) {
  if (typeof cents !== "number" || !Number.isFinite(cents)) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
}

function formatOrderTotal(order: Order) {
  const cents = typeof order.total_cents === "number" ? order.total_cents : order.valor_total;
  return moneyFromCents(cents);
}

function formatDateTime(date?: string | null) {
  if (!date) return "—";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(date));
}

function normalizeText(value?: string | number | null) {
  return String(value ?? "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function OrderStatusBadge({ status }: { status?: string | null }) {
  const presentation = getOrderStatusPresentation(status);
  const Icon = presentation.icon;
  return (
    <Badge variant="outline" className={cn("gap-1.5 border px-2.5 py-1 font-medium", statusToneClasses[presentation.tone])}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {presentation.label}
    </Badge>
  );
}

function OrdersPageHeader({ onRefresh, isRefreshing }: { onRefresh: () => void; isRefreshing: boolean }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p className="text-sm font-medium text-brand-600">Service Delivery</p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Pedidos</h1>
        <p className="mt-1 text-sm text-slate-500">Acompanhe e gerencie os pedidos da sua loja.</p>
      </div>
      <Button type="button" variant="outline" onClick={onRefresh} disabled={isRefreshing} className="gap-2 self-start">
        <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
        Atualizar
      </Button>
    </div>
  );
}

function OrdersSummaryCards({ orders }: { orders: Order[] }) {
  const today = new Date().toLocaleDateString("pt-BR");
  const stats = [
    { label: "Pedidos hoje", value: orders.filter((order) => new Date(order.created_at).toLocaleDateString("pt-BR") === today).length, icon: ShoppingBag },
    { label: "Pendentes", value: orders.filter((order) => ["PENDING", "RECEBIDO", "pending"].includes(order.status)).length, icon: Clock3 },
    { label: "Em preparo", value: orders.filter((order) => ["EM_PREPARO", "PREPARANDO", "PREPARING"].includes(order.status)).length, icon: Timer },
    { label: "Em entrega", value: orders.filter((order) => ["DRIVER_ASSIGNED", "ASSIGNED", "SAIU_PARA_ENTREGA", "OUT_FOR_DELIVERY", "IN_TRANSIT"].includes(order.status)).length, icon: Truck },
    { label: "Concluídos", value: orders.filter((order) => ["ENTREGUE", "DELIVERED"].includes(order.status)).length, icon: CheckCircle2 },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <Card key={stat.label} className="border-slate-200 bg-white/90 shadow-sm">
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="text-xs font-medium text-slate-500">{stat.label}</p>
                <p className="mt-1 text-2xl font-semibold text-slate-950">{stat.value}</p>
              </div>
              <div className="rounded-2xl bg-brand-50 p-2.5 text-brand-600"><Icon className="h-5 w-5" /></div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

interface Filters { order: string; customer: string; status: string; payment: string; delivery: string; date: string; }

function OrdersFilters({ filters, setFilters, orders }: { filters: Filters; setFilters: (filters: Filters) => void; orders: Order[] }) {
  const payments = Array.from(new Set(orders.map((order) => order.forma_pagamento).filter(Boolean)));
  const deliveries = Array.from(new Set(orders.map((order) => order.tipo_entrega || order.order_type || "").filter(Boolean)));
  const clearFilters = () => setFilters({ order: "", customer: "", status: "", payment: "", delivery: "", date: "" });

  return (
    <Card className="border-slate-200 shadow-sm">
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800"><Filter className="h-4 w-4" /> Filtros</div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_0.9fr_0.9fr_0.9fr_0.9fr_auto]">
          <div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input className="pl-9" placeholder="Buscar pedido" value={filters.order} onChange={(e) => setFilters({ ...filters, order: e.target.value })} /></div>
          <div className="relative"><UserRound className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input className="pl-9" placeholder="Buscar cliente" value={filters.customer} onChange={(e) => setFilters({ ...filters, customer: e.target.value })} /></div>
          <Select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}><option value="">Todos status</option>{statusFilterOptions.map((status) => <option key={status} value={status}>{getOrderStatusPresentation(status).label}</option>)}</Select>
          <Select value={filters.payment} onChange={(e) => setFilters({ ...filters, payment: e.target.value })}><option value="">Pagamento</option>{payments.map((payment) => <option key={payment} value={payment}>{payment}</option>)}</Select>
          <Select value={filters.delivery} onChange={(e) => setFilters({ ...filters, delivery: e.target.value })}><option value="">Entrega</option>{deliveries.map((delivery) => <option key={delivery} value={delivery}>{delivery}</option>)}</Select>
          <Input type="date" value={filters.date} onChange={(e) => setFilters({ ...filters, date: e.target.value })} />
          <Button type="button" variant="ghost" onClick={clearFilters} className="gap-2"><X className="h-4 w-4" /> Limpar</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function OrdersEmptyState({ filtered }: { filtered?: boolean }) {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-8 text-center">
      <div className="rounded-3xl bg-white p-4 text-brand-600 shadow-sm"><PackageOpen className="h-8 w-8" /></div>
      <h2 className="mt-4 text-base font-semibold text-slate-950">{filtered ? "Nenhum resultado para os filtros" : "Nenhum pedido encontrado"}</h2>
      <p className="mt-1 max-w-sm text-sm text-slate-500">{filtered ? "Ajuste ou limpe os filtros para visualizar outros pedidos." : "Quando novos pedidos chegarem, eles aparecerão aqui."}</p>
    </div>
  );
}

function OrderActionsMenu({ order, onDetails, onWhatsApp, canWhatsApp }: { order: Order; onDetails: () => void; onWhatsApp: (event: MouseEvent<HTMLButtonElement>) => void; canWhatsApp: boolean }) {
  const copy = (value: string) => navigator.clipboard?.writeText(value);
  return (
    <details className="group relative" onClick={(event) => event.stopPropagation()}>
      <summary className="inline-flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-md border border-slate-200 bg-white hover:bg-slate-50"><MoreVertical className="h-4 w-4" /></summary>
      <div className="absolute right-0 z-20 mt-2 w-56 rounded-xl border border-slate-200 bg-white p-1 text-sm shadow-xl">
        <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-slate-50" onClick={onDetails}><ChevronRight className="h-4 w-4" /> Ver detalhes</button>
        <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-slate-50 disabled:text-slate-400" disabled={!canWhatsApp} onClick={onWhatsApp}><MessageCircle className="h-4 w-4" /> WhatsApp</button>
        <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-slate-50" onClick={() => copy(getCustomerPhone(order))}><Phone className="h-4 w-4" /> Copiar telefone</button>
        <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-slate-50" onClick={() => copy(String(getOrderNumber(order)))}><Copy className="h-4 w-4" /> Copiar número</button>
      </div>
    </details>
  );
}

function OrdersTable({ orders, selectedOrderId, onSelect, onWhatsApp }: { orders: Order[]; selectedOrderId: number | null; onSelect: (order: Order) => void; onWhatsApp: (event: MouseEvent<HTMLButtonElement>, order: Order) => void }) {
  return (
    <div className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:block">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur">
          <TableRow className="border-slate-200">
            <TableHead>Pedido</TableHead><TableHead>Cliente</TableHead><TableHead>Data</TableHead><TableHead>Total</TableHead><TableHead>Status</TableHead><TableHead>Entrega</TableHead><TableHead>Pagamento</TableHead><TableHead className="text-right">Ações</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orders.map((order) => {
            const phone = getCustomerPhone(order);
            const canWhatsApp = Boolean(normalizeWhatsAppPhone(phone) && buildOrderWhatsAppUrl(order));
            const selected = selectedOrderId === order.id;
            return (
              <TableRow key={order.id} onClick={() => onSelect(order)} className={cn("cursor-pointer border-slate-100 transition-colors hover:bg-brand-50/40", selected && "bg-brand-50/70 ring-1 ring-inset ring-brand-200")}>
                <TableCell className="py-4"><div className="font-semibold text-slate-950">#{getOrderNumber(order)}</div><div className="text-xs text-slate-500">ID {order.id}</div></TableCell>
                <TableCell className="py-4"><div className="flex items-center gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">{getCustomerName(order).charAt(0).toUpperCase()}</div><div className="min-w-0"><p className="truncate font-medium text-slate-900">{getCustomerName(order)}</p><p className="truncate text-xs text-slate-500">{phone || "Telefone não informado"}</p></div></div></TableCell>
                <TableCell className="py-4 whitespace-nowrap text-sm text-slate-600">{formatDateTime(order.created_at)}</TableCell>
                <TableCell className="py-4 whitespace-nowrap font-semibold text-slate-950">{formatOrderTotal(order)}</TableCell>
                <TableCell className="py-4"><OrderStatusBadge status={order.status} /></TableCell>
                <TableCell className="py-4 text-sm text-slate-600">{order.tipo_entrega || order.order_type || "—"}</TableCell>
                <TableCell className="py-4 text-sm text-slate-600">{order.forma_pagamento || "—"}</TableCell>
                <TableCell className="py-4 text-right"><div className="flex justify-end gap-2"><Button type="button" variant="outline" size="icon" disabled={!canWhatsApp} title="Enviar mensagem pelo WhatsApp" aria-label="Enviar mensagem pelo WhatsApp" onClick={(event) => onWhatsApp(event, order)} className="h-9 w-9 border-emerald-200 text-emerald-700 hover:bg-emerald-50"><MessageCircle className="h-4 w-4" /></Button><OrderActionsMenu order={order} canWhatsApp={canWhatsApp} onDetails={() => onSelect(order)} onWhatsApp={(event) => onWhatsApp(event, order)} /></div></TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function OrdersMobileCards({ orders, onSelect, onWhatsApp }: { orders: Order[]; onSelect: (order: Order) => void; onWhatsApp: (event: MouseEvent<HTMLButtonElement>, order: Order) => void }) {
  return <div className="space-y-3 lg:hidden">{orders.map((order) => { const phone = getCustomerPhone(order); const canWhatsApp = Boolean(normalizeWhatsAppPhone(phone)); return <Card key={order.id} className="border-slate-200 shadow-sm"><CardContent className="space-y-3 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-950">Pedido #{getOrderNumber(order)}</p><p className="text-sm text-slate-600">{getCustomerName(order)}</p><p className="text-xs text-slate-500">{phone || "Telefone não informado"}</p></div><OrderStatusBadge status={order.status} /></div><div className="grid grid-cols-2 gap-3 text-sm"><div><p className="text-xs text-slate-500">Total</p><p className="font-semibold">{formatOrderTotal(order)}</p></div><div><p className="text-xs text-slate-500">Entrega</p><p>{order.tipo_entrega || order.order_type || "—"}</p></div></div><div className="flex gap-2"><Button type="button" variant="outline" className="flex-1 gap-2" onClick={() => onSelect(order)}>Detalhes</Button><Button type="button" variant="outline" size="icon" disabled={!canWhatsApp} title="Enviar mensagem pelo WhatsApp" onClick={(event) => onWhatsApp(event, order)} className="border-emerald-200 text-emerald-700"><MessageCircle className="h-4 w-4" /></Button></div></CardContent></Card>; })}</div>;
}

function OrderTimeline({ order }: { order: Order }) {
  const current = getOrderStatusPresentation(order.status).label;
  const steps = [
    { label: "Recebido", at: order.created_at, active: true },
    { label: "Confirmado", at: order.confirmed_at, active: ["Confirmado", "Em preparo", "Pronto para entrega", "Entregador atribuído", "Saiu para entrega", "Entregue"].includes(current) },
    { label: "Em preparo", at: order.preparing_at, active: ["Em preparo", "Pronto para entrega", "Entregador atribuído", "Saiu para entrega", "Entregue"].includes(current) },
    { label: "Pronto", at: order.ready_at, active: ["Pronto para entrega", "Entregador atribuído", "Saiu para entrega", "Entregue"].includes(current) },
    { label: "Saiu para entrega", at: order.start_delivery_at, active: ["Saiu para entrega", "Entregue"].includes(current) },
    { label: "Entregue", at: order.delivered_at, active: current === "Entregue" },
  ];
  return <div className="space-y-3">{steps.map((step) => <div key={step.label} className="flex gap-3"><div className={cn("mt-1 h-3 w-3 rounded-full border", step.active ? "border-brand-600 bg-brand-600" : "border-slate-300 bg-white")} /><div><p className={cn("text-sm font-medium", step.active ? "text-slate-900" : "text-slate-400")}>{step.label}</p>{step.at && <p className="text-xs text-slate-500">{formatDateTime(step.at)}</p>}</div></div>)}</div>;
}

function OrderItemsList({ items, isLoading }: { items?: OrderItem[]; isLoading: boolean }) {
  if (isLoading) return <div className="space-y-2">{[0, 1, 2].map((item) => <div key={item} className="h-16 animate-pulse rounded-xl bg-slate-100" />)}</div>;
  if (!items?.length) return <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-500">Nenhum item detalhado disponível para este pedido.</p>;
  return <ul className="space-y-2">{items.map((item) => <li key={item.id} className="rounded-xl border border-slate-200 p-3"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-medium text-slate-900">{item.quantity}x {item.name}</p>{Boolean(item.modifiers?.length) && <p className="mt-1 text-xs text-slate-500">Adicionais: {item.modifiers?.map((mod) => mod.name).join(", ")}</p>}{item.notes && <p className="mt-1 text-xs text-slate-500">Obs: {item.notes}</p>}</div><p className="whitespace-nowrap text-sm font-semibold">{moneyFromCents(item.subtotal_cents)}</p></div></li>)}</ul>;
}

function OrderDetailsPanel({ order, items, isItemsLoading, onClose, onWhatsApp, updateStatus, isMobile }: { order?: Order; items?: OrderItem[]; isItemsLoading: boolean; onClose: () => void; onWhatsApp: (event: MouseEvent<HTMLButtonElement>, order: Order) => void; updateStatus: UpdateStatusMutation; isMobile?: boolean }) {
  if (!order) return <aside className="hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm xl:block"><div className="flex min-h-[520px] flex-col items-center justify-center text-center"><div className="rounded-3xl bg-brand-50 p-4 text-brand-600"><FileText className="h-9 w-9" /></div><h2 className="mt-4 text-base font-semibold text-slate-950">Selecione um pedido</h2><p className="mt-1 max-w-xs text-sm text-slate-500">Os detalhes do cliente, entrega, pagamento, itens e timeline aparecerão aqui.</p></div></aside>;
  const phone = getCustomerPhone(order); const hasWhatsApp = Boolean(normalizeWhatsAppPhone(phone));
  return <aside className={cn("rounded-2xl border border-slate-200 bg-white shadow-sm", isMobile ? "fixed inset-x-0 bottom-0 z-40 max-h-[92vh] overflow-y-auto rounded-b-none p-4 lg:hidden" : "hidden max-h-[calc(100vh-2rem)] overflow-y-auto p-5 xl:block")}><div className="space-y-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-medium text-slate-500">Pedido</p><h2 className="text-xl font-semibold text-slate-950">#{getOrderNumber(order)}</h2><p className="text-xs text-slate-500">{formatDateTime(order.created_at)}</p></div><div className="flex items-center gap-2"><OrderStatusBadge status={order.status} /><Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Fechar detalhes"><X className="h-4 w-4" /></Button></div></div><section className="rounded-2xl bg-slate-50 p-4"><h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><UserRound className="h-4 w-4" /> Cliente</h3><p className="font-medium">{getCustomerName(order)}</p><p className="text-sm text-slate-500">{phone || "Telefone não informado"}</p><Button type="button" className="mt-3 w-full gap-2 bg-emerald-600 hover:bg-emerald-700" disabled={!hasWhatsApp} onClick={(event) => onWhatsApp(event, order)}><MessageCircle className="h-4 w-4" /> Enviar atualização no WhatsApp</Button></section><section className="space-y-2"><h3 className="flex items-center gap-2 text-sm font-semibold"><MapPin className="h-4 w-4" /> Entrega</h3><div className="rounded-xl border border-slate-200 p-3 text-sm text-slate-600"><p><strong>Tipo:</strong> {order.tipo_entrega || order.order_type || "—"}</p><p><strong>Endereço:</strong> {order.endereco || "—"}</p>{order.complemento && <p><strong>Complemento:</strong> {order.complemento}</p>}{order.bairro && <p><strong>Bairro:</strong> {order.bairro}</p>}{order.cidade && <p><strong>Cidade:</strong> {order.cidade}</p>}{order.referencia && <p><strong>Referência:</strong> {order.referencia}</p>}<p><strong>Entregador:</strong> {order.assigned_delivery_user_name || order.assigned_delivery_user_id || "—"}</p><p><strong>Status entrega:</strong> {order.delivery_status ? getOrderStatusPresentation(order.delivery_status).label : getOrderStatusPresentation(order.status).label}</p></div></section><section className="space-y-2"><h3 className="flex items-center gap-2 text-sm font-semibold"><CreditCard className="h-4 w-4" /> Pagamento</h3><div className="grid grid-cols-2 gap-2 text-sm"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Forma</p><p className="font-medium">{order.forma_pagamento || "—"}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Valor</p><p className="font-medium">{formatOrderTotal(order)}</p></div>{(order.change_for || order.troco_para) && <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Troco para</p><p className="font-medium">{moneyFromCents(order.change_for || order.troco_para)}</p></div>}{order.payment_status && <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Status</p><p className="font-medium">{order.payment_status}</p></div>}</div></section><section className="space-y-2"><h3 className="text-sm font-semibold">Itens</h3><OrderItemsList items={items} isLoading={isItemsLoading} /><div className="rounded-xl bg-slate-950 p-3 text-sm text-white"><div className="flex justify-between"><span>Subtotal</span><span>{moneyFromCents(order.subtotal ?? undefined)}</span></div><div className="flex justify-between text-slate-300"><span>Taxa</span><span>{moneyFromCents(order.delivery_fee ?? undefined)}</span></div><div className="mt-2 flex justify-between text-base font-semibold"><span>Total</span><span>{formatOrderTotal(order)}</span></div></div></section>{order.observacao && <section className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"><strong>Observação:</strong> {order.observacao}</section>}<section className="space-y-2"><h3 className="text-sm font-semibold">Timeline</h3><OrderTimeline order={order} /></section><section className="space-y-2"><p className="text-sm font-semibold text-slate-700">Ações rápidas</p><div className="flex flex-wrap gap-2">{statusOptions.map((status) => <Button key={status} variant="outline" size="sm" onClick={() => updateStatus.mutate({ orderId: order.id, status })}>{getOrderStatusPresentation(status).label}</Button>)}</div>{updateStatus.isError && <p className="text-xs text-red-600">Erro ao atualizar status.</p>}</section></div></aside>;
}

export default function OrdersPage() {
  const queryClient = useQueryClient();
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [whatsAppError, setWhatsAppError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({ order: "", customer: "", status: "", payment: "", delivery: "", date: "" });
  const { data: session, isLoading: isSessionLoading } = useSession();
  const tenantId = session?.tenant_id;

  const { data: orders, isLoading, isError, isFetching, refetch } = useQuery({ queryKey: ["orders", tenantId], queryFn: () => api.get<Order[]>(`/api/orders/${tenantId}`), enabled: Boolean(tenantId) });
  const orderItemsQuery = useQuery({ queryKey: ["order-items", selectedOrderId], queryFn: () => api.get<OrderItem[]>(`/api/orders/${selectedOrderId}/items`), enabled: Boolean(selectedOrderId) });
  const updateStatus = useMutation({ mutationFn: ({ orderId, status }: { orderId: number; status: string }) => api.patch(`/api/orders/${orderId}/status`, { status }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["orders"] }); if (selectedOrderId) queryClient.invalidateQueries({ queryKey: ["order-items", selectedOrderId] }); } });

  const selectedOrder = useMemo(() => orders?.find((order) => order.id === selectedOrderId), [orders, selectedOrderId]);
  const filteredOrders = useMemo(() => (orders || []).filter((order) => {
    const orderNumber = normalizeText(getOrderNumber(order));
    const customer = normalizeText(getCustomerName(order));
    const status = (order.status || "").toUpperCase();
    const date = order.created_at?.slice(0, 10);
    return (!filters.order || orderNumber.includes(normalizeText(filters.order)) || String(order.id).includes(filters.order)) && (!filters.customer || customer.includes(normalizeText(filters.customer))) && (!filters.status || status === filters.status || getOrderStatusPresentation(status).label === getOrderStatusPresentation(filters.status).label) && (!filters.payment || order.forma_pagamento === filters.payment) && (!filters.delivery || (order.tipo_entrega || order.order_type) === filters.delivery) && (!filters.date || date === filters.date);
  }), [orders, filters]);

  function handleSelect(order: Order) { setSelectedOrderId(order.id); }
  function handleWhatsAppClick(event: MouseEvent<HTMLButtonElement>, order: Order) { event.stopPropagation(); setWhatsAppError(null); const opened = openOrderWhatsApp(order); if (!opened) setWhatsAppError("Este cliente não possui um telefone válido para WhatsApp."); }

  if (isSessionLoading || isLoading) return <div className="space-y-4"><div className="h-20 animate-pulse rounded-2xl bg-slate-100" /><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{[0,1,2,3,4].map((i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-slate-100" />)}</div><div className="h-96 animate-pulse rounded-2xl bg-slate-100" /></div>;
  if (!tenantId || isError || !orders) return <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700"><p className="font-semibold">Não foi possível carregar pedidos.</p><p className="mt-1">Verifique sua sessão e tente novamente.</p><Button type="button" variant="outline" className="mt-4" onClick={() => refetch()}>Tentar novamente</Button></div>;

  return <div className="space-y-5"><OrdersPageHeader onRefresh={() => refetch()} isRefreshing={isFetching} /><OrdersSummaryCards orders={orders} />{whatsAppError && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">{whatsAppError}</div>}<OrdersFilters filters={filters} setFilters={setFilters} orders={orders} /><div className="grid gap-5 xl:grid-cols-[minmax(0,72fr)_minmax(320px,28fr)]"><main className="min-w-0 space-y-3">{orders.length === 0 ? <OrdersEmptyState /> : filteredOrders.length === 0 ? <OrdersEmptyState filtered /> : <><OrdersTable orders={filteredOrders} selectedOrderId={selectedOrderId} onSelect={handleSelect} onWhatsApp={handleWhatsAppClick} /><OrdersMobileCards orders={filteredOrders} onSelect={handleSelect} onWhatsApp={handleWhatsAppClick} /></>}</main><OrderDetailsPanel order={selectedOrder} items={orderItemsQuery.data} isItemsLoading={orderItemsQuery.isLoading} onClose={() => setSelectedOrderId(null)} onWhatsApp={handleWhatsAppClick} updateStatus={updateStatus} />{selectedOrder && <OrderDetailsPanel order={selectedOrder} items={orderItemsQuery.data} isItemsLoading={orderItemsQuery.isLoading} onClose={() => setSelectedOrderId(null)} onWhatsApp={handleWhatsAppClick} updateStatus={updateStatus} isMobile />}</div></div>;
}
