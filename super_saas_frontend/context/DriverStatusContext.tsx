"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type DriverStatusContextValue = {
  online: boolean;
  isHydrated: boolean;
  setOnline: () => Promise<void>;
  setOffline: () => Promise<void>;
};

const DRIVER_ONLINE_STORAGE_KEY = "driver_online_status";

const DriverStatusContext = createContext<DriverStatusContextValue | null>(null);

function persistOnlineStatus(nextOnline: boolean) {
  localStorage.setItem(DRIVER_ONLINE_STORAGE_KEY, JSON.stringify(nextOnline));
}

export function DriverStatusProvider({ children }: { children: React.ReactNode }) {
  const [online, setOnlineState] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    const storedStatus = localStorage.getItem(DRIVER_ONLINE_STORAGE_KEY);

    if (storedStatus !== null) {
      setOnlineState(storedStatus === "true");
    }

    setIsHydrated(true);
  }, []);

  const setOnline = useCallback(async () => {
    setOnlineState(true);
    persistOnlineStatus(true);
  }, []);

  const setOffline = useCallback(async () => {
    setOnlineState(false);
    persistOnlineStatus(false);
  }, []);

  const value = useMemo(
    () => ({
      online,
      isHydrated,
      setOnline,
      setOffline,
    }),
    [isHydrated, online, setOffline, setOnline],
  );

  return <DriverStatusContext.Provider value={value}>{children}</DriverStatusContext.Provider>;
}

export function useDriverStatusContext() {
  const context = useContext(DriverStatusContext);

  if (!context) {
    console.warn("useDriverStatusContext called without DriverStatusProvider. Falling back to offline state.");
    return {
      online: false,
      isHydrated: true,
      setOnline: async () => undefined,
      setOffline: async () => undefined,
    };
  }

  return context;
}
