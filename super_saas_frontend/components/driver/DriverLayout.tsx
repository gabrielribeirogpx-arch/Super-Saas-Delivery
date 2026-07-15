"use client";

import { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { clearDriverSession } from "@/lib/driverAuth";
import { DriverBottomNav, DriverHeader } from "@/components/driver/DriverUI";

export default function DriverLayout({ title, children, name, offline, gpsActive, hasRoute }: { title: string; children: ReactNode; name?: string; offline?: boolean; gpsActive?: boolean; hasRoute?: boolean }) {
  const router = useRouter();
  const logout = () => {
    clearDriverSession();
    router.replace("/driver/login");
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#ecfdf5_0,_#f8fafc_38%,_#eef2f7_100%)] text-slate-950">
      <div className="mx-auto min-h-screen w-full max-w-3xl px-4 pb-28 md:px-6 md:pb-8">
        <DriverHeader title={title} name={name} offline={offline} gpsActive={gpsActive} onLogout={logout} />
        {children}
      </div>
      <DriverBottomNav active="home" hasRoute={hasRoute} />
    </main>
  );
}
