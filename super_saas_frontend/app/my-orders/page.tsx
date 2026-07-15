"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { resolveStorefrontTenant } from "@/lib/storefrontApi";
export default function MyOrdersPage() {
  const [tokens, setTokens] = useState<string[]>([]);
  useEffect(() => {
    const tenant = resolveStorefrontTenant() || window.location.hostname.split(".")[0] || "unknown";
    setTokens(JSON.parse(window.localStorage.getItem(`service-delivery:${tenant}:customer-orders`) || "[]"));
  }, []);
  return <main className="mx-auto min-h-screen max-w-md bg-slate-50 p-4 pb-24"><h1 className="text-2xl font-bold">Meus pedidos</h1><p className="mt-2 text-sm text-slate-600">MVP seguro: este dispositivo mostra apenas pedidos criados aqui, salvos pelo tracking_token público do pedido.</p><div className="mt-4 space-y-3">{tokens.length ? tokens.map((token) => <Link className="block rounded-2xl bg-white p-4 shadow-sm" href={`/my-orders/${token}`} key={token}>Pedido {token.slice(0, 8)}…<span className="block text-xs text-slate-500">Ver status e rastreamento</span></Link>) : <p className="rounded-2xl bg-white p-4 text-sm text-slate-500">Nenhum pedido salvo neste dispositivo.</p>}</div></main>;
}
