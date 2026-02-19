"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface AppearanceSettings {
  primary_color: string;
  secondary_color: string;
  button_radius: number;
  hero_image_url?: string;
  logo_url?: string;
  font_family: string;
  layout_variant: "clean" | "modern" | "commercial";
}

const CACHE_KEY = "admin-appearance-cache";

const defaultAppearance: AppearanceSettings = {
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

export function useAppearance() {
  const [appearance, setAppearance] = useState<AppearanceSettings>(defaultAppearance);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const cached = window.localStorage.getItem(CACHE_KEY);
    if (!cached) {
      return;
    }

    try {
      const parsed = JSON.parse(cached);
      if (isAppearanceSettings(parsed)) {
        setAppearance(parsed);
      }
    } catch {
      window.localStorage.removeItem(CACHE_KEY);
    }
  }, []);

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
          window.localStorage.setItem(CACHE_KEY, JSON.stringify(response));
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
  }, []);

  const updateAppearance = (next: AppearanceSettings) => {
    setAppearance(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(CACHE_KEY, JSON.stringify(next));
    }
  };

  const saveAppearance = async (data: AppearanceSettings) => {
    const response = await api.put<AppearanceSettings>("/api/appearance", data);
    updateAppearance(response);
    return response;
  };

  return { appearance, setAppearance: updateAppearance, saveAppearance, loading };
}
