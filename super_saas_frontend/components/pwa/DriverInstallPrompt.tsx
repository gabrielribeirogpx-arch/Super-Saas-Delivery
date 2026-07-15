"use client";

import { useEffect, useState } from "react";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};

const isIos = () => /iphone|ipad|ipod/i.test(window.navigator.userAgent);
const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches ||
  Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);

export default function DriverInstallPrompt() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [standalone, setStandalone] = useState(false);
  const [ios, setIos] = useState(false);

  useEffect(() => {
    setStandalone(isStandalone());
    setIos(isIos());

    const onBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      console.info("[PWA] beforeinstallprompt received.");
      setInstallEvent(event as BeforeInstallPromptEvent);
    };
    const onAppInstalled = () => {
      console.info("[PWA] appinstalled received.");
      setInstallEvent(null);
      setStandalone(true);
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  if (standalone) return null;

  if (installEvent) {
    return (
      <button
        type="button"
        className="fixed bottom-4 right-4 z-[9997] rounded-full bg-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-xl"
        onClick={async () => {
          await installEvent.prompt();
          const choice = await installEvent.userChoice;
          console.info("[PWA] install prompt choice.", choice);
          setInstallEvent(null);
        }}
      >
        Instalar aplicativo
      </button>
    );
  }

  if (ios) {
    return (
      <div className="fixed bottom-4 right-4 z-[9997] max-w-xs rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs font-medium text-slate-800 shadow-xl">
        Abra Compartilhar e selecione Adicionar à Tela de Início.
      </div>
    );
  }

  return null;
}
