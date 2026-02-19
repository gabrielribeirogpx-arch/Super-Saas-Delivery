"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";

export interface AppearanceTheme {
  primary_color: string | null;
  accent_color: string | null;
  background_color: string | null;
  surface_color: string | null;
  button_radius: number | null;
  card_radius: number | null;
  cover_image_url: string | null;
  logo_url: string | null;
  hero_overlay_opacity: number | null;
}

const DEFAULT_THEME: AppearanceTheme = {
  primary_color: null,
  accent_color: null,
  background_color: null,
  surface_color: null,
  button_radius: null,
  card_radius: null,
  cover_image_url: null,
  logo_url: null,
  hero_overlay_opacity: null,
};

export function useAppearanceEditor(initialTheme?: Partial<AppearanceTheme>) {
  const [originalTheme, setOriginalTheme] = useState<AppearanceTheme>({
    ...DEFAULT_THEME,
    ...initialTheme,
  });
  const [draftTheme, setDraftTheme] = useState<AppearanceTheme>({
    ...DEFAULT_THEME,
    ...initialTheme,
  });
  const [isSaving, setIsSaving] = useState(false);

  const isDirty = useMemo(
    () => JSON.stringify(originalTheme) !== JSON.stringify(draftTheme),
    [draftTheme, originalTheme]
  );

  const setFromRemote = (theme: Partial<AppearanceTheme>) => {
    const next = { ...DEFAULT_THEME, ...theme };
    setOriginalTheme(next);
    setDraftTheme(next);
  };

  const save = async () => {
    setIsSaving(true);
    try {
      const saved = await api.put<AppearanceTheme>("/api/store/theme", draftTheme);
      setOriginalTheme(saved);
      setDraftTheme(saved);
      return saved;
    } finally {
      setIsSaving(false);
    }
  };

  const reset = () => {
    setDraftTheme(originalTheme);
  };

  return {
    draftTheme,
    setDraftTheme,
    originalTheme,
    isDirty,
    isSaving,
    save,
    reset,
    setFromRemote,
  };
}
