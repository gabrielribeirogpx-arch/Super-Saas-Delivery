"use client";

import { useEffect, useState } from "react";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
import { loadCustomerSession, saveCustomerSession } from "@/components/storefront/customerSession";

type Profile = { id: number; name: string; phone: string; email?: string | null; addresses: Array<{ id: number; street: string; number: string; neighborhood: string; city: string }> };

export default function ProfilePage({ params }: { params: { slug: string } }) {
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    const session = loadCustomerSession(params.slug);
    if (!session?.customerId) return;
    fetch(`/api/store/customer-profile?customer_id=${session.customerId}`, { credentials: "include" })
      .then((res) => res.json())
      .then(setProfile)
      .catch(() => setProfile(null));
  }, [params.slug]);

  const save = async () => {
    if (!profile) return;
    const response = await fetch(`/api/store/customer-profile/${profile.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: profile.name, phone: profile.phone, email: profile.email }),
      credentials: "include",
    });
    if (!response.ok) return;
    const data = await response.json();
    setProfile(data);
    saveCustomerSession(params.slug, { customerId: data.id, name: data.name, phone: data.phone, email: data.email ?? undefined });
  };

  return (
    <main className="p-4 pb-24">
      <h1 className="mb-4 text-xl font-semibold">Profile</h1>
      {profile && (
        <div className="space-y-2">
          <input className="w-full rounded border p-2" value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} placeholder="Name" />
          <input className="w-full rounded border p-2" value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} placeholder="Phone" />
          <input className="w-full rounded border p-2" value={profile.email ?? ""} onChange={(e) => setProfile({ ...profile, email: e.target.value })} placeholder="Email" />
          <button onClick={save} className="rounded bg-black px-3 py-2 text-sm text-white">Save profile</button>
          <h2 className="pt-2 font-medium">Saved addresses</h2>
          {profile.addresses.map((address) => <p key={address.id} className="text-sm">{address.street}, {address.number} - {address.neighborhood} / {address.city}</p>)}
        </div>
      )}
      <CustomerBottomNav slug={params.slug} />
    </main>
  );
}
