"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
}

function platformHelp() {
  const agent = navigator.userAgent;
  if (/iphone|ipad|ipod/i.test(agent)) {
    return "Toque em Compartilhar e escolha Adicionar à Tela de Início. Se essa opção não aparecer, abra o cardápio no Safari.";
  }
  if (/android/i.test(agent)) {
    return "Abra o menu do navegador (⋮) e escolha Instalar app ou Adicionar à tela inicial. Se a opção não aparecer, tente no Chrome.";
  }
  return "Abra o link desta loja no celular para adicionar o cardápio à tela inicial.";
}

export default function CustomerInstallPrompt({ storeName }: { storeName?: string | null }) {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstallEvent(null);
      setShowHelp(false);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  useEffect(() => {
    const onInstallClick = async () => {
      if (isStandalone()) return;
      if (installEvent) {
        setInstallEvent(null);
        try {
          await installEvent.prompt();
          const choice = await installEvent.userChoice;
          if (choice.outcome === "accepted") return;
        } catch {
          // The browser may reject a stale prompt. Show its manual install path.
        }
      }
      setShowHelp(true);
    };
    window.addEventListener("customer-pwa-install-click", onInstallClick);
    return () => window.removeEventListener("customer-pwa-install-click", onInstallClick);
  }, [installEvent]);

  if (!showHelp) return null;

  return (
    <div className="fixed inset-x-3 bottom-[calc(var(--customer-bottom-nav-height)+var(--customer-cart-bar-height)+var(--customer-safe-bottom)+0.75rem)] z-[var(--customer-z-overlay)] mx-auto max-w-sm rounded-2xl border border-slate-200 bg-white p-4 pr-12 text-sm text-slate-900 shadow-xl" role="dialog" aria-label={`Como instalar o cardápio da ${storeName || "loja"}`}>
      <button type="button" className="absolute right-2 top-2 flex h-11 w-11 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900" onClick={() => setShowHelp(false)} aria-label="Fechar instruções de instalação">
        <X className="h-5 w-5" aria-hidden="true" />
      </button>
      <p className="font-semibold">Instalar cardápio da {storeName || "loja"}</p>
      <p className="mt-2 leading-5 text-slate-600">{platformHelp()}</p>
    </div>
  );
}
