"use client";

import { useEffect, useState } from "react";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
import { buildStorefrontApiUrl } from "@/lib/storefrontApi";
import { loadCustomerSession } from "@/components/storefront/customerSession";

export default function AddressesPage({ params }: { params: { slug: string } }) {
  const [addresses, setAddresses] = useState<Array<{ id: number; street: string; number: string; neighborhood: string; city: string; cep: string }>>([]);

  useEffect(() => {
    const session = loadCustomerSession(params.slug);
    if (!session?.customerId) return;
    fetch(buildStorefrontApiUrl(`/api/store/customer-profile?customer_id=${session.customerId}`), { credentials: "include" })
      .then((res) => res.json())
      .then((data) => setAddresses(data.addresses || []));
  }, [params.slug]);

  return (
    <main className="p-4 pb-24">
      <h1 className="mb-4 text-xl font-semibold">Addresses</h1>
      {addresses.map((address) => <p key={address.id} className="mb-2 rounded border p-2 text-sm">{address.cep} • {address.street}, {address.number} - {address.neighborhood} / {address.city}</p>)}
      <CustomerBottomNav slug={params.slug} />
    </main>
  );
}
