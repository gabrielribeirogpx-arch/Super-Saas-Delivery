"use client";

import { useEffect } from "react";

import { useStoreAppearance } from "@/hooks/useStoreAppearance";

export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  const { appearance } = useStoreAppearance();

  useEffect(() => {
    document.documentElement.style.setProperty("--primary-color", appearance.primary_color);
    document.documentElement.style.setProperty("--secondary-color", appearance.secondary_color);
    document.documentElement.style.setProperty("--button-radius", `${appearance.button_radius}px`);
    document.documentElement.style.setProperty("--font-family", appearance.font_family);
  }, [appearance]);

  return <>{children}</>;
}
