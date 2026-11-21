"use client";

import { useEffect, useState } from "react";

import { PublicMenuPage } from "@/components/PublicMenu/PublicMenuPage";
import type { PublicMenuResponse } from "@/components/storefront/types";
import styles from "./page.module.css";

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

  useEffect(() => {
    if (!preview) return;

    const content = document.querySelector<HTMLElement>("[data-preview-content]");
    if (!content) return;

    let lastHeight = 0;
    const reportHeight = () => {
      const height = Math.ceil(content.getBoundingClientRect().height);
      if (height === lastHeight) return;
      lastHeight = height;
      window.parent.postMessage({ type: "storefront-preview:height", height }, window.location.origin);
    };
    const observer = new ResizeObserver(reportHeight);
    observer.observe(content);
    window.addEventListener("resize", reportHeight);
    reportHeight();

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", reportHeight);
    };
  }, [preview]);

  if (!preview) return <p className="p-5 text-sm text-slate-500">Abra esta prévia pelo painel da loja.</p>;

  return (
    <div data-preview-content className={styles.embed} onClickCapture={(event) => {
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
