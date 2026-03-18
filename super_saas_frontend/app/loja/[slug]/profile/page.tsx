"use client";

import { useEffect, useMemo, useState } from "react";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
import { CustomerProfileSnapshot, loadCustomerSession, saveCustomerProfileSnapshot } from "@/components/storefront/customerSession";

type Profile = {
  id: number;
  name: string;
  phone: string;
  email?: string | null;
  addresses: Array<{ id: number; street: string; number: string; neighborhood: string; city: string }>;
};

export default function ProfilePage({ params }: { params: { slug: string } }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const session = loadCustomerSession(params.slug) as CustomerProfileSnapshot | null;
    if (!session?.customerId) return;
    setProfile({
      id: session.customerId,
      name: session.name ?? "",
      phone: session.phone ?? "",
      email: session.email ?? null,
      addresses: Array.isArray(session.addresses) ? session.addresses : [],
    });
  }, [params.slug]);

  const hasProfile = useMemo(() => Boolean(profile), [profile]);

  const save = () => {
    if (!profile) return;
    saveCustomerProfileSnapshot(params.slug, {
      customerId: profile.id,
      name: profile.name,
      phone: profile.phone,
      email: profile.email ?? undefined,
      addresses: profile.addresses,
    });
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  };

  return (
    <main className="p-4 pb-24">
      <h1 className="mb-4 text-xl font-semibold">Profile</h1>
      {!hasProfile ? (
        <p className="text-sm text-slate-500">Faça um pedido primeiro para preencher seus dados automaticamente.</p>
      ) : null}
      {profile && (
        <div className="space-y-2">
          <p className="rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">
            Seus dados são mantidos apenas neste dispositivo enquanto o endpoint público de perfil não está disponível.
          </p>
          <input className="w-full rounded border p-2" value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} placeholder="Name" />
          <input className="w-full rounded border p-2" value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} placeholder="Phone" />
          <input className="w-full rounded border p-2" value={profile.email ?? ""} onChange={(e) => setProfile({ ...profile, email: e.target.value })} placeholder="Email" />
          <button onClick={save} className="rounded bg-black px-3 py-2 text-sm text-white">Save profile</button>
          {saved ? <p className="text-sm text-emerald-600">Perfil salvo neste dispositivo.</p> : null}
          <h2 className="pt-2 font-medium">Saved addresses</h2>
          {profile.addresses.length === 0 ? <p className="text-sm text-slate-500">Nenhum endereço salvo ainda.</p> : null}
          {profile.addresses.map((address) => <p key={address.id} className="text-sm">{address.street}, {address.number} - {address.neighborhood} / {address.city}</p>)}
        </div>
      )}
      <CustomerBottomNav slug={params.slug} />
    </main>
  );
}
