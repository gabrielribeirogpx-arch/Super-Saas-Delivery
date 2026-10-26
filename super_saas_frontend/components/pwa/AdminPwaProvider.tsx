"use client";

import { createContext, useContext, useEffect, useState } from "react";

type InstallEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

type InstallState = {
  ready: boolean;
  installed: boolean;
  canPrompt: boolean;
  install: () => Promise<"accepted" | "dismissed" | "unavailable">;
};

const AdminPwaContext = createContext<InstallState | null>(null);

function isInstalled() {
  return window.matchMedia("(display-mode: standalone)").matches ||
    Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);
}

export function AdminPwaProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [installEvent, setInstallEvent] = useState<InstallEvent | null>(null);

  useEffect(() => {
    setInstalled(isInstalled());
    setReady(true);
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as InstallEvent);
    };
    const onInstalled = () => {
      setInstallEvent(null);
      setInstalled(true);
    };
    const mode = window.matchMedia("(display-mode: standalone)");
    const onModeChange = () => setInstalled(isInstalled());
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    mode.addEventListener("change", onModeChange);

    // The customer and restaurant PWAs share a safe, network-only service worker for admin routes.
    // Registering the same worker avoids replacing the customer's root-scope registration.
    navigator.serviceWorker?.register("/customer-sw.js", { scope: "/" }).catch(() => undefined);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
      mode.removeEventListener("change", onModeChange);
    };
  }, []);

  const install = async (): Promise<"accepted" | "dismissed" | "unavailable"> => {
    if (!installEvent) return "unavailable";
    try {
      await installEvent.prompt();
      const choice = await installEvent.userChoice;
      setInstallEvent(null);
      return choice.outcome;
    } catch {
      setInstallEvent(null);
      return "unavailable";
    }
  };

  return <AdminPwaContext.Provider value={{ ready, installed, canPrompt: Boolean(installEvent) && !installed, install }}>{children}</AdminPwaContext.Provider>;
}

export function useAdminPwaInstall() {
  const context = useContext(AdminPwaContext);
  if (!context) throw new Error("useAdminPwaInstall requires AdminPwaProvider");
  return context;
}
