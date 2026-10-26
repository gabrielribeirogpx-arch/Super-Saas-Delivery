"use client";

import styles from "./Driver.module.css";
import { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { clearDriverSession } from "@/lib/driverAuth";
import { DriverBottomNav, DriverHeader } from "@/components/driver/DriverUI";

export default function DriverLayout({ title, children, name, offline, gpsActive, hasRoute, routeId }: { title: string; children: ReactNode; name?: string; offline?: boolean; gpsActive?: boolean; hasRoute?: boolean; routeId?: number }) {
  const router = useRouter();
  const logout = () => {
    clearDriverSession();
    router.replace("/driver/login");
  };

  return (
    <main className={styles.app}>
      <div className={styles.container}>
        <DriverHeader title={title} name={name} offline={offline} gpsActive={gpsActive} onLogout={logout} />
        {children}
      </div>
      <DriverBottomNav active="home" hasRoute={hasRoute} routeId={routeId} />
    </main>
  );
}
