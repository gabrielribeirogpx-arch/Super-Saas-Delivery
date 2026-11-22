"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { customerMe, logoutCustomer, customerAccountUrl, customerTenant } from "@/lib/customerAuth";
type Customer = {
  name: string | null;
  verification_method: "phone" | "email";
  phone_masked?: string;
  email_masked?: string;
  loyalty?: { enabled: boolean; available_points: number; lifetime_points: number };
};
export default function Account() {
  const [me, setMe] = useState<Customer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tenant, setTenant] = useState("");
  const accountHref = (path: string) => tenant ? `${path}?tenant=${encodeURIComponent(tenant)}` : path;
  const router = useRouter();
  useEffect(() => {
    let active = true;
    setTenant(customerTenant());
    void customerMe().then(customer => {
      if (!active) return;
      if (customer) setMe(customer); else router.replace(customerAccountUrl("/account/login"));
    }).catch(() => { if (active) setError("Não foi possível carregar sua conta. Tente novamente."); });
    return () => { active = false; };
  }, [router]);
  return <main className="mx-auto min-h-screen max-w-md p-6 pb-24">
    <h1 className="text-2xl font-black">Minha conta</h1>
    {me && <div className="mt-4 rounded-2xl border p-4"><p className="font-bold">{me.name || "Cliente"}</p><p className="text-sm text-slate-600">{me.verification_method === "email" ? `E-mail verificado: ${me.email_masked}` : `Telefone verificado: ${me.phone_masked}`}</p>{me.verification_method === "email" && <p className="text-sm text-slate-600">Celular para contato: {me.phone_masked}</p>}</div>}
    {me?.loyalty?.enabled && <section className="mt-4 overflow-hidden rounded-2xl bg-slate-950 p-5 text-white" aria-label="Programa de pontos">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/60">Seus pontos</p>
      <p className="mt-2 text-3xl font-black">{me.loyalty.available_points.toLocaleString("pt-BR")}</p>
      <p className="mt-1 text-sm text-white/70">pontos disponíveis</p>
      <div className="mt-4 border-t border-white/15 pt-3 text-xs text-white/60">
        {me.loyalty.lifetime_points > 0
          ? `${me.loyalty.lifetime_points.toLocaleString("pt-BR")} pontos acumulados desde o início`
          : "Faça pedidos nesta loja para começar a acumular pontos."}
      </div>
    </section>}
    {error && <p role="alert" className="mt-3 text-red-600">{error}</p>}
    <div className="mt-6 grid gap-3">
      <Link className="rounded-xl border p-4 font-semibold" href={accountHref("/account/orders")}>Pedidos</Link>
      <Link className="rounded-xl border p-4 font-semibold" href={accountHref("/account/addresses")}>Endereços</Link>
      <button disabled={busy} className="rounded-xl bg-slate-100 p-4 font-semibold" onClick={async () => {
        setBusy(true); setError("");
        try { await logoutCustomer(); router.replace(customerAccountUrl("/account/login")); }
        catch { setError("Não foi possível encerrar a sessão. Tente novamente."); }
        finally { setBusy(false); }
      }}>Sair</button>
    </div>
  </main>;
}
