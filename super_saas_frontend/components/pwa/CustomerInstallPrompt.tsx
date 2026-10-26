"use client";
import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { resolveStorefrontTenant } from "@/lib/storefrontApi";
type BeforeInstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };
const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);
const isIos = () => /iphone|ipad|ipod/i.test(window.navigator.userAgent);
const isSafari = () => /^((?!chrome|android|crios|fxios).)*safari/i.test(window.navigator.userAgent);
const isAndroid = () => /android/i.test(window.navigator.userAgent);
const isDesktop = () => !/android|iphone|ipad|ipod/i.test(window.navigator.userAgent);
export default function CustomerInstallPrompt({ storeName }: { storeName?: string | null }) {
  const [event, setEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [showIos, setShowIos] = useState(false);
  const tenant = useMemo(() => resolveStorefrontTenant(), []);
  const storageKey = `service-delivery:${tenant || "unknown"}:customer-install-dismissed`;
  useEffect(() => {
    if (window.location.pathname.startsWith("/driver") || isStandalone() || isDesktop()) return;
    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      if (isAndroid() && window.localStorage.getItem(storageKey) !== "1") {
        setEvent(e as BeforeInstallPromptEvent);
      }
    };
    const onInstalled = () => setEvent(null);
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    if (isIos() && isSafari() && window.localStorage.getItem(storageKey) !== "1") setShowIos(true);
    return () => { window.removeEventListener("beforeinstallprompt", onBeforeInstall); window.removeEventListener("appinstalled", onInstalled); };
  }, [storageKey]);
  useEffect(() => {
    const onInstallClick = async () => {
      if (event) { await event.prompt(); await event.userChoice; setEvent(null); }
      else if (isIos() && isSafari()) setShowIos(true);
    };
    window.addEventListener("customer-pwa-install-click", onInstallClick);
    return () => window.removeEventListener("customer-pwa-install-click", onInstallClick);
  }, [event]);
  if (!event && !showIos) return null;
  const name = storeName || "loja";
  const dismiss = () => {
    window.localStorage.setItem(storageKey, "1");
    setEvent(null);
    setShowIos(false);
  };
  return <div className="fixed inset-x-3 bottom-[calc(var(--customer-bottom-nav-height)+var(--customer-cart-bar-height)+var(--customer-safe-bottom)+0.75rem)] z-[var(--customer-z-overlay)] mx-auto max-w-sm rounded-2xl border border-slate-200 bg-white p-3 pr-11 text-sm shadow-xl md:hidden" role="status">
    <button type="button" className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900" onClick={dismiss} aria-label="Fechar aviso de instalação">
      <X className="h-4 w-4" aria-hidden="true" />
    </button>
    {event ? <div className="flex items-center gap-3"><p className="min-w-0 flex-1 font-semibold">Instalar app da {name}</p><button type="button" className="shrink-0 rounded-xl bg-slate-950 px-4 py-2 font-semibold text-white" onClick={async () => { await event.prompt(); await event.userChoice; setEvent(null); }}>Instalar</button></div> : <><p className="font-semibold">Instalar app da {name}</p><p className="mt-1 text-slate-600">Toque em Compartilhar e depois em Adicionar à Tela de Início.</p></>}
  </div>;
}
