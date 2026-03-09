"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/services/api";
import { ensureDriverOnline, setDriverOffline } from "@/services/delivery";

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
    const status = await ensureDriverOnline();
    console.debug("Driver online status from backend:", status);
    const isOnlineInBackend = status !== "OFFLINE";

    setOnlineState(isOnlineInBackend);
    persistOnlineStatus(isOnlineInBackend);

    if (!isOnlineInBackend) {
      throw new Error("Driver is still offline in backend");
    }
  }, []);

  const setOffline = useCallback(async () => {
    try {
      await setDriverOffline();
    } catch (err) {
      if (!(err instanceof ApiError && err.response?.status === 409)) {
        throw err;
      }
    }

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
