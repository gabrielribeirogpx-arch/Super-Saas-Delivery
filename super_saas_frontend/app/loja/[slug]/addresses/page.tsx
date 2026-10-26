"use client";

import { useEffect, useState } from "react";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
import { loadCustomerSession } from "@/components/storefront/customerSession";

type Address = { id: number; street: string; number: string; neighborhood: string; city: string; cep: string };

export default function AddressesPage({ params }: { params: { slug: string } }) {
  const [addresses, setAddresses] = useState<Address[]>([]);

  useEffect(() => {
    const session = loadCustomerSession(params.slug) as { addresses?: Address[] } | null;
    setAddresses(Array.isArray(session?.addresses) ? session.addresses : []);
  }, [params.slug]);

  return (
    <main className="p-4 pb-24">
      <h1 className="mb-4 text-xl font-semibold">Addresses</h1>
      {addresses.length === 0 ? <p className="text-sm text-slate-500">Nenhum endereço salvo neste dispositivo.</p> : null}
      {addresses.map((address) => <p key={address.id} className="mb-2 rounded border p-2 text-sm">{address.cep} • {address.street}, {address.number} - {address.neighborhood} / {address.city}</p>)}
      <CustomerBottomNav slug={params.slug} />
    </main>
  );
}
