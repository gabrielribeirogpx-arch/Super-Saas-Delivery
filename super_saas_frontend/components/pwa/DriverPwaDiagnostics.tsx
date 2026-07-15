"use client";

import { useEffect, useState } from "react";

type DiagnosticState = {
  manifestUrl: string;
  manifestLoaded: boolean;
  serviceWorkerRegistered: boolean;
  serviceWorkerControlsPage: boolean;
  scope: string;
  beforeInstallPromptReceived: boolean;
  standalone: boolean;
  iconsAccessible: Record<string, boolean>;
  reason: string;
};

const defaultState: DiagnosticState = {
  manifestUrl: "/manifest.webmanifest",
  manifestLoaded: false,
  serviceWorkerRegistered: false,
  serviceWorkerControlsPage: false,
  scope: "",
  beforeInstallPromptReceived: false,
  standalone: false,
  iconsAccessible: {},
  reason: "Aguardando diagnóstico do navegador.",
};

export default function DriverPwaDiagnostics() {
  const [state, setState] = useState(defaultState);

  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;

    const onBeforeInstallPrompt = () => setState((current) => ({ ...current, beforeInstallPromptReceived: true }));
    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);

    const run = async () => {
      const manifestLink = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
      const manifestUrl = manifestLink?.href || `${window.location.origin}/manifest.webmanifest`;
      const iconPaths = ["/icons/driver-icon.svg", "/icons/maskable-icon.svg"];
      const iconsAccessible = Object.fromEntries(
        await Promise.all(iconPaths.map(async (icon) => [icon, (await fetch(icon, { cache: "no-store" })).ok])),
      );
      const registration = "serviceWorker" in navigator ? await navigator.serviceWorker.getRegistration("/driver") : undefined;
      const manifestLoaded = (await fetch(manifestUrl, { cache: "no-store" })).ok;
      const standalone = window.matchMedia("(display-mode: standalone)").matches || Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);
      const serviceWorkerControlsPage = Boolean(navigator.serviceWorker?.controller);
      const reason = !manifestLoaded
        ? "Manifest não carregou."
        : !registration
          ? "Service worker ainda não registrado para /driver."
          : !serviceWorkerControlsPage
            ? "Service worker registrado, mas esta navegação ainda não está controlada; recarregue /driver."
            : Object.values(iconsAccessible).some((ok) => !ok)
              ? "Um ou mais ícones não estão acessíveis."
              : "Requisitos básicos locais encontrados; aguarde beforeinstallprompt do Chrome.";

      setState((current) => ({
        ...current,
        manifestUrl,
        manifestLoaded,
        serviceWorkerRegistered: Boolean(registration),
        serviceWorkerControlsPage,
        scope: registration?.scope || "",
        standalone,
        iconsAccessible,
        reason,
      }));
    };

    void run().catch((error) => setState((current) => ({ ...current, reason: `Falha no diagnóstico: ${String(error)}` })));

    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
  }, []);

  if (process.env.NODE_ENV === "production") return null;

  return (
    <details className="fixed bottom-4 left-4 z-[9996] max-w-sm rounded-2xl border border-slate-300 bg-white p-3 text-xs text-slate-900 shadow-xl">
      <summary className="cursor-pointer font-semibold">Diagnóstico PWA</summary>
      <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap">{JSON.stringify(state, null, 2)}</pre>
    </details>
  );
}
