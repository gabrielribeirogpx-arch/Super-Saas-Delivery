"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { customerMe, logoutCustomer, customerAccountUrl, customerTenant } from "@/lib/customerAuth";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
type Customer = { name: string | null; phone_masked: string };
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
    });
    return () => { active = false; };
  }, [router]);
  return <main className="mx-auto min-h-screen max-w-md p-6 pb-24">
    <h1 className="text-2xl font-black">Minha conta</h1>
    {me && <div className="mt-4 rounded-2xl border p-4"><p className="font-bold">{me.name || "Cliente"}</p><p className="text-sm text-slate-600">Telefone verificado: {me.phone_masked}</p></div>}
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
    <CustomerBottomNav />
  </main>;
}
