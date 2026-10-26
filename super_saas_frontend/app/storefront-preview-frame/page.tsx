"use client";

import { useEffect, useState } from "react";

import { PublicMenuPage } from "@/components/PublicMenu/PublicMenuPage";
import type { PublicMenuResponse } from "@/components/storefront/types";

type PreviewPayload = { type: "storefront-preview:update"; menu: PublicMenuResponse; theme: "white" | "dark" };

export default function StorefrontPreviewFrame() {
  const [preview, setPreview] = useState<PreviewPayload | null>(null);

  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== window.parent) return;
      const data = event.data as PreviewPayload | null;
      if (data?.type !== "storefront-preview:update" || !data.menu?.slug || !Array.isArray(data.menu.categories) || !["white", "dark"].includes(data.theme)) return;
      setPreview(data);
    };
    window.addEventListener("message", receive);
    window.parent.postMessage({ type: "storefront-preview:ready" }, window.location.origin);
    return () => window.removeEventListener("message", receive);
  }, []);

  if (!preview) return <p className="p-5 text-sm text-slate-500">Abra esta prévia pelo painel da loja.</p>;

  return (
    <div onClickCapture={(event) => {
      if (event.target instanceof Element && event.target.closest("a[href]")) event.preventDefault();
    }}>
      <PublicMenuPage
        menu={preview.menu}
        enableCart={false}
        forcedTheme={preview.theme}
        onPreviewThemeChange={(theme) => window.parent.postMessage({ type: "storefront-preview:theme", theme }, window.location.origin)}
      />
    </div>
  );
}
