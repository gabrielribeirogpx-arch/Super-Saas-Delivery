"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { AppearanceSettings } from "@/hooks/useAppearance";

export const defaultAppearance: AppearanceSettings = {
  primary_color: "#2563eb",
  secondary_color: "#111827",
  button_radius: 12,
  font_family: "Inter",
  layout_variant: "clean",
};

function isAppearanceSettings(value: unknown): value is AppearanceSettings {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<AppearanceSettings>;
  return (
    typeof candidate.primary_color === "string" &&
    typeof candidate.secondary_color === "string" &&
    typeof candidate.button_radius === "number" &&
    typeof candidate.font_family === "string" &&
    (candidate.layout_variant === "clean" ||
      candidate.layout_variant === "modern" ||
      candidate.layout_variant === "commercial")
  );
}

export function useStoreAppearance() {
  const [appearance, setAppearance] = useState<AppearanceSettings>(defaultAppearance);
  const [loading, setLoading] = useState(true);

  const cacheKey = useMemo(() => {
    if (typeof window === "undefined") {
      return "store-appearance-cache";
    }

    return `store-appearance-cache:${window.location.host}`;
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const cached = window.localStorage.getItem(cacheKey);
    if (!cached) {
      return;
    }

    try {
      const parsed = JSON.parse(cached);
      if (isAppearanceSettings(parsed)) {
        setAppearance(parsed);
      }
    } catch {
      window.localStorage.removeItem(cacheKey);
    }
  }, [cacheKey]);

  useEffect(() => {
    let active = true;

    api
      .get<AppearanceSettings>("/api/appearance")
      .then((response) => {
        if (!active) {
          return;
        }

        setAppearance(response);
        if (typeof window !== "undefined") {
          window.localStorage.setItem(cacheKey, JSON.stringify(response));
        }
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setAppearance((current) => current ?? defaultAppearance);
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [cacheKey]);

  return { appearance, loading };
}
